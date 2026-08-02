package com.mimotrust.xiaozhen.overlay

import android.animation.ValueAnimator
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.IBinder
import android.provider.Settings
import android.text.TextUtils
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.app.NotificationCompat
import com.mimotrust.xiaozhen.MainActivity
import com.mimotrust.xiaozhen.MimoTrustApplication
import com.mimotrust.xiaozhen.R
import com.mimotrust.xiaozhen.data.local.JobEntity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.roundToInt

enum class FloatingBallState {
    Idle, Attention, Queued, Resolving, Searching, Finishing, Completed, Failed,
}

class FloatingBallService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private lateinit var windowManager: WindowManager
    private var ballView: FloatingBallView? = null
    private var layoutParams: WindowManager.LayoutParams? = null
    private var activeJobId: String? = null
    private var requestInFlight = false
    private var jobsCollector: Job? = null
    private var resultPopup: View? = null
    private var lastPopupJobId: String? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIFICATION_ID, serviceNotification())
        if (Settings.canDrawOverlays(this)) showBall()
        observeJobs()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_ATTENTION -> if (!requestInFlight && activeJobId == null) {
                ballView?.setState(FloatingBallState.Attention, 0)
            }
            ACTION_RESOLVING -> {
                ballView?.setState(FloatingBallState.Resolving, REQUEST_ACCEPTED_PROGRESS)
            }
            ACTION_FAILED -> {
                requestInFlight = false
                ballView?.setState(FloatingBallState.Failed, 0)
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        jobsCollector?.cancel()
        scope.cancel()
        ballView?.stopAnimation()
        ballView?.let { runCatching { windowManager.removeView(it) } }
        resultPopup?.let { runCatching { windowManager.removeView(it) } }
        resultPopup = null
        ballView = null
        super.onDestroy()
    }

    private fun showBall() {
        if (ballView != null) return
        windowManager = getSystemService(WindowManager::class.java)
        val size = (68 * resources.displayMetrics.density).toInt()
        val params = WindowManager.LayoutParams(
            size,
            size,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            android.graphics.PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = resources.displayMetrics.widthPixels - size - 18
            y = resources.displayMetrics.heightPixels / 3
        }
        layoutParams = params
        val view = FloatingBallView(this) { expanded -> resizeBall(expanded) }.apply {
            contentDescription = "小真悬浮核验"
            setOnTouchListener(BallTouchListener())
        }
        ballView = view
        windowManager.addView(view, params)
    }

    private fun resizeBall(expanded: Boolean) {
        val params = layoutParams ?: return
        val density = resources.displayMetrics.density
        val targetWidth = ((if (expanded) 168 else 68) * density).toInt()
        if (params.width == targetWidth) return
        val rightEdge = params.x + params.width
        params.width = targetWidth
        params.x = (rightEdge - targetWidth).coerceIn(
            0,
            resources.displayMetrics.widthPixels - targetWidth,
        )
        ballView?.let { windowManager.updateViewLayout(it, params) }
    }

    private fun verifyCurrentVideo() {
        if (activeJobId != null) {
            openApp(activeJobId)
            return
        }
        if (requestInFlight) {
            Toast.makeText(this, "正在获取当前视频，请稍候", Toast.LENGTH_SHORT).show()
            return
        }
        requestInFlight = true
        val requestId = ControlledContentRequestCoordinator.request(this)
        Log.i(LOG_TAG, "CONTENT_CONTEXT_REQUEST_SENT request_id=$requestId")
        ballView?.setState(FloatingBallState.Queued, REQUEST_SENT_PROGRESS)
        ballView?.postDelayed({
            if (ControlledContentRequestCoordinator.isPending(this, requestId)) {
                ControlledContentRequestCoordinator.cancel(this, requestId)
                requestInFlight = false
                ballView?.setState(FloatingBallState.Failed, 0)
                Toast.makeText(this, "未获取到当前视频，请保持视频平台在前台后重试", Toast.LENGTH_LONG).show()
            }
        }, ControlledContentRequestCoordinator.RESPONSE_TIMEOUT_MS)
    }

    private fun observeJobs() {
        jobsCollector = scope.launch {
            (application as MimoTrustApplication).repository.observeJobs().collectLatest { jobs ->
                val tracked = jobs.firstOrNull { it.status == "queued" || it.status == "running" }
                    ?: activeJobId?.let { id -> jobs.firstOrNull { it.jobId == id } }
                if (tracked != null) {
                    requestInFlight = false
                    val isNewJob = tracked.jobId != activeJobId
                    activeJobId = tracked.jobId
                    if (isNewJob) ballView?.setState(FloatingBallState.Idle, 0)
                    ballView?.setState(mapState(tracked), tracked.progress)
                    if (tracked.status in setOf("completed", "failed", "cancelled") &&
                        lastPopupJobId != tracked.jobId
                    ) {
                        lastPopupJobId = tracked.jobId
                        showResultPopup(tracked)
                    }
                    if (tracked.status !in setOf("queued", "running")) {
                        ballView?.postDelayed({ activeJobId = null }, 4_000)
                    }
                } else if (ballView?.state !in setOf(FloatingBallState.Attention, FloatingBallState.Completed, FloatingBallState.Failed)) {
                    ballView?.setState(FloatingBallState.Idle, 0)
                }
            }
        }
    }

    private fun mapState(job: JobEntity): FloatingBallState = when {
        job.status == "completed" -> FloatingBallState.Completed
        job.status == "failed" || job.status == "cancelled" -> FloatingBallState.Failed
        job.status == "queued" -> FloatingBallState.Queued
        job.stage in setOf("content_resolving", "media_extracting", "claim_structuring") -> FloatingBallState.Resolving
        job.stage in setOf("evidence_retrieval", "evidence_triage") -> FloatingBallState.Searching
        job.stage == "report_generating" -> FloatingBallState.Finishing
        job.progress < 45 -> FloatingBallState.Resolving
        job.progress < 85 -> FloatingBallState.Searching
        else -> FloatingBallState.Finishing
    }

    private fun openApp(jobId: String?) {
        startActivity(Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            jobId?.let { putExtra("job_id", it) }
        })
    }

    private fun showResultPopup(job: JobEntity) {
        resultPopup?.let { runCatching { windowManager.removeView(it) } }
        val failed = job.status == "failed" || job.status == "cancelled"
        val density = resources.displayMetrics.density
        fun dp(value: Int) = (value * density).toInt()
        fun text(value: String, size: Float, color: Int, bold: Boolean = false) = TextView(this).apply {
            this.text = value
            setTextSize(TypedValue.COMPLEX_UNIT_SP, size)
            setTextColor(color)
            if (bold) setTypeface(typeface, Typeface.BOLD)
            maxLines = 2
            ellipsize = TextUtils.TruncateAt.END
        }

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12))
            elevation = dp(12).toFloat()
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = dp(22).toFloat()
                setColor(Color.WHITE)
                setStroke(dp(2), if (failed) 0xFFD94841.toInt() else 0xFF25A75A.toInt())
            }
        }
        content.addView(ImageView(this).apply {
            setImageResource(R.drawable.xiaozhen_floating_ball)
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(if (failed) 0xFFFFE9E7.toInt() else 0xFFE7F7ED.toInt())
            }
            setPadding(dp(3), dp(3), dp(3), dp(3))
        }, LinearLayout.LayoutParams(dp(58), dp(58)))
        content.addView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), 0, 0, 0)
            addView(text(
                if (failed) "核验未完成" else "核验完成 · ${job.verdict ?: "查看结果"}",
                15f,
                0xFF201713.toInt(),
                bold = true,
            ))
            addView(text(
                if (failed) job.displayText else job.headline ?: "小真已完成核验",
                12.5f,
                if (failed) 0xFFD94841.toInt() else 0xFF25A75A.toInt(),
                bold = true,
            ))
            addView(text(job.conclusion ?: "点击查看完整详情", 11f, 0xFF8F827C.toInt()))
        }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        content.setOnClickListener {
            dismissResultPopup()
            openApp(job.jobId)
        }

        val params = WindowManager.LayoutParams(
            resources.displayMetrics.widthPixels - dp(28),
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            android.graphics.PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            y = dp(72)
        }
        resultPopup = content
        windowManager.addView(content, params)
        content.alpha = 0f
        content.translationY = -dp(18).toFloat()
        content.animate().alpha(1f).translationY(0f).setDuration(220L).start()
        content.postDelayed({ if (resultPopup === content) dismissResultPopup() }, RESULT_POPUP_DURATION_MS)
    }

    private fun dismissResultPopup() {
        val popup = resultPopup ?: return
        resultPopup = null
        popup.animate().alpha(0f).translationY(-24f).setDuration(160L).withEndAction {
            runCatching { windowManager.removeView(popup) }
        }.start()
    }

    private fun serviceNotification(): android.app.Notification {
        val intent = PendingIntent.getActivity(
            this,
            9102,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_shield)
            .setContentTitle("小真悬浮核验已开启")
            .setContentText("点击悬浮球即可核实当前视频")
            .setContentIntent(intent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun createChannel() {
        val channel = NotificationChannel(CHANNEL_ID, "悬浮核验", NotificationManager.IMPORTANCE_LOW).apply {
            description = "保持用户主动开启的小真悬浮球运行"
            setSound(null, null)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private inner class BallTouchListener : View.OnTouchListener {
        private var downRawX = 0f
        private var downRawY = 0f
        private var startX = 0
        private var startY = 0

        override fun onTouch(view: View, event: MotionEvent): Boolean {
            val params = layoutParams ?: return false
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downRawX = event.rawX
                    downRawY = event.rawY
                    startX = params.x
                    startY = params.y
                    return true
                }
                MotionEvent.ACTION_MOVE -> {
                    params.x = startX + (event.rawX - downRawX).toInt()
                    params.y = startY + (event.rawY - downRawY).toInt()
                    windowManager.updateViewLayout(view, params)
                    return true
                }
                MotionEvent.ACTION_UP -> {
                    val moved = abs(event.rawX - downRawX) + abs(event.rawY - downRawY)
                    if (moved < 18 * resources.displayMetrics.density) {
                        view.performClick()
                        verifyCurrentVideo()
                    }
                    return true
                }
            }
            return false
        }
    }

    companion object {
        const val ACTION_ATTENTION = "com.mimotrust.xiaozhen.action.FLOATING_BALL_ATTENTION"
        const val ACTION_RESOLVING = "com.mimotrust.xiaozhen.action.FLOATING_BALL_RESOLVING"
        const val ACTION_FAILED = "com.mimotrust.xiaozhen.action.FLOATING_BALL_FAILED"
        private const val LOG_TAG = "MiMoTrustGuardian"
        private const val REQUEST_SENT_PROGRESS = 6
        private const val REQUEST_ACCEPTED_PROGRESS = 14
        private const val CHANNEL_ID = "mimo_floating_ball"
        private const val NOTIFICATION_ID = 9101
        private const val RESULT_POPUP_DURATION_MS = 10_000L
    }
}

private class FloatingBallView(
    context: Context,
    private val onExpandedChanged: (Boolean) -> Unit,
) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val ringRect = RectF()
    private val clipPath = Path()
    private val logo: Bitmap = BitmapFactory.decodeResource(resources, R.drawable.xiaozhen_floating_ball)
    var state: FloatingBallState = FloatingBallState.Idle
        private set
    private var displayedProgress = 0f
    private var attentionAnimator: ValueAnimator? = null
    private var progressAnimator: ValueAnimator? = null

    fun setState(value: FloatingBallState, progressValue: Int) {
        val wasExpanded = state.isExpanded()
        state = value
        if (wasExpanded != value.isExpanded()) onExpandedChanged(value.isExpanded())
        val targetProgress = progressValue.coerceIn(0, 100).toFloat()
        if (value in setOf(
                FloatingBallState.Queued,
                FloatingBallState.Resolving,
                FloatingBallState.Searching,
                FloatingBallState.Finishing,
                FloatingBallState.Completed,
            )
        ) {
            animateProgressTo(if (value == FloatingBallState.Completed) 100f else targetProgress)
        } else {
            progressAnimator?.cancel()
            displayedProgress = 0f
        }
        if (value == FloatingBallState.Attention) startAttentionAnimation() else stopAnimation()
        invalidate()
        if (value == FloatingBallState.Completed || value == FloatingBallState.Failed) {
            postDelayed({ if (state == value) setState(FloatingBallState.Idle, 0) }, 4_000)
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (state.isExpanded()) drawExpanded(canvas) else drawCompact(canvas)
    }

    private fun drawCompact(canvas: Canvas) {
        val centerX = width / 2f
        val centerY = height / 2f
        val radius = width.coerceAtMost(height) * .43f
        paint.style = Paint.Style.FILL
        paint.color = Color.WHITE
        paint.setShadowLayer(12f, 0f, 4f, 0x35000000)
        setLayerType(LAYER_TYPE_SOFTWARE, paint)
        canvas.drawCircle(centerX, centerY, radius, paint)
        paint.clearShadowLayer()

        drawAvatar(canvas, centerX, centerY, radius, stateColor(), stateSweep())
    }

    private fun drawExpanded(canvas: Canvas) {
        val inset = 4f * resources.displayMetrics.density
        val corner = height / 2f
        paint.style = Paint.Style.FILL
        paint.color = Color.WHITE
        paint.setShadowLayer(12f, 0f, 4f, 0x35000000)
        setLayerType(LAYER_TYPE_SOFTWARE, paint)
        canvas.drawRoundRect(inset, inset, width - inset, height - inset, corner, corner, paint)
        paint.clearShadowLayer()

        val centerX = height / 2f
        val centerY = height / 2f
        val radius = height * .37f
        drawAvatar(canvas, centerX, centerY, radius, stateColor(), stateSweep())

        val textLeft = height * .91f
        paint.style = Paint.Style.FILL
        paint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        paint.textSize = 13f * resources.displayMetrics.scaledDensity
        paint.color = 0xFF201713.toInt()
        canvas.drawText(stateLabel(), textLeft, height * .43f, paint)

        paint.typeface = Typeface.DEFAULT
        paint.textSize = 10.5f * resources.displayMetrics.scaledDensity
        paint.color = 0xFF8F827C.toInt()
        val detail = when (state) {
            FloatingBallState.Completed -> "点击查看结果"
            FloatingBallState.Failed -> "点击查看原因"
            else -> "${displayedProgress.roundToInt()}% · 后台处理中"
        }
        canvas.drawText(detail, textLeft, height * .68f, paint)

        if (state !in setOf(FloatingBallState.Completed, FloatingBallState.Failed)) {
            val barLeft = textLeft
            val barRight = width - 14f * resources.displayMetrics.density
            val barY = height - 9f * resources.displayMetrics.density
            paint.strokeWidth = 3f * resources.displayMetrics.density
            paint.strokeCap = Paint.Cap.ROUND
            paint.color = 0xFFE8E2DF.toInt()
            canvas.drawLine(barLeft, barY, barRight, barY, paint)
            paint.color = stateColor()
            canvas.drawLine(
                barLeft,
                barY,
                barLeft + (barRight - barLeft) * displayedProgress.coerceIn(0f, 100f) / 100f,
                barY,
                paint,
            )
        }
    }

    private fun drawAvatar(
        canvas: Canvas,
        centerX: Float,
        centerY: Float,
        radius: Float,
        ringColor: Int,
        sweep: Float,
    ) {
        clipPath.reset()
        clipPath.addCircle(centerX, centerY, radius - 4f, Path.Direction.CW)
        canvas.save()
        canvas.clipPath(clipPath)
        canvas.drawBitmap(
            logo,
            Rect(0, 0, logo.width, logo.height),
            RectF(centerX - radius, centerY - radius, centerX + radius, centerY + radius),
            paint,
        )
        canvas.restore()

        paint.style = Paint.Style.STROKE
        paint.strokeWidth = radius * .15f
        paint.strokeCap = Paint.Cap.ROUND
        paint.color = if (state == FloatingBallState.Idle) 0x33201713 else ringColor.and(0x00FFFFFF) or 0x33000000
        ringRect.set(centerX - radius, centerY - radius, centerX + radius, centerY + radius)
        canvas.drawArc(ringRect, -90f, 360f, false, paint)
        paint.color = ringColor
        canvas.drawArc(ringRect, -90f, sweep, false, paint)
    }

    private fun stateColor(): Int = when (state) {
        FloatingBallState.Attention, FloatingBallState.Queued, FloatingBallState.Resolving -> 0xFFFF5A1F.toInt()
        FloatingBallState.Searching -> 0xFF4F7FE8.toInt()
        FloatingBallState.Finishing -> 0xFF8A62D6.toInt()
        FloatingBallState.Completed -> 0xFF25A75A.toInt()
        FloatingBallState.Failed -> 0xFFD94841.toInt()
        FloatingBallState.Idle -> 0xFF201713.toInt()
    }

    private fun stateSweep(): Float = when (state) {
        FloatingBallState.Idle -> 0f
        FloatingBallState.Attention, FloatingBallState.Failed -> 360f
        else -> 360f * displayedProgress / 100f
    }

    private fun stateLabel(): String = when (state) {
        FloatingBallState.Queued -> "已接收"
        FloatingBallState.Resolving -> "解析视频"
        FloatingBallState.Searching -> "检索证据"
        FloatingBallState.Finishing -> "生成报告"
        FloatingBallState.Completed -> "核验完成"
        FloatingBallState.Failed -> "核验失败"
        FloatingBallState.Attention -> "可以核验"
        FloatingBallState.Idle -> "小真"
    }

    private fun FloatingBallState.isExpanded(): Boolean = this !in setOf(
        FloatingBallState.Idle,
        FloatingBallState.Attention,
    )

    private fun animateProgressTo(target: Float) {
        if (target <= displayedProgress || kotlin.math.abs(target - displayedProgress) < .1f) {
            displayedProgress = maxOf(displayedProgress, target)
            invalidate()
            return
        }
        progressAnimator?.cancel()
        progressAnimator = ValueAnimator.ofFloat(displayedProgress, target).apply {
            duration = 650L
            addUpdateListener {
                displayedProgress = it.animatedValue as Float
                invalidate()
            }
            start()
        }
    }

    private fun startAttentionAnimation() {
        if (attentionAnimator?.isRunning == true) return
        attentionAnimator = ValueAnimator.ofFloat(1f, .38f, 1f).apply {
            duration = 820
            repeatCount = ValueAnimator.INFINITE
            addUpdateListener { alpha = it.animatedValue as Float }
            start()
        }
    }

    fun stopAnimation() {
        attentionAnimator?.cancel()
        attentionAnimator = null
        alpha = 1f
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }
}
