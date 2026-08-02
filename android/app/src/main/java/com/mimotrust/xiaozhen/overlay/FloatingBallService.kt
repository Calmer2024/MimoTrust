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
import android.os.IBinder
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Toast
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

enum class FloatingBallState {
    Idle, Attention, Queued, Resolving, Searching, Finishing, Completed, Failed,
}

class FloatingBallService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var windowManager: WindowManager
    private var ballView: FloatingBallView? = null
    private var layoutParams: WindowManager.LayoutParams? = null
    private var activeJobId: String? = null
    private var requestInFlight = false
    private var jobsCollector: Job? = null

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
        val view = FloatingBallView(this).apply {
            contentDescription = "小真悬浮核验"
            setOnTouchListener(BallTouchListener())
        }
        ballView = view
        windowManager.addView(view, params)
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
                val tracked = activeJobId?.let { id -> jobs.firstOrNull { it.jobId == id } }
                    ?: jobs.firstOrNull { it.status == "queued" || it.status == "running" }
                if (tracked != null) {
                    requestInFlight = false
                    val isNewJob = tracked.jobId != activeJobId
                    activeJobId = tracked.jobId
                    ballView?.post {
                        if (isNewJob) ballView?.setState(FloatingBallState.Idle, 0)
                        ballView?.setState(mapState(tracked), tracked.progress)
                    }
                    if (tracked.status !in setOf("queued", "running")) {
                        ballView?.postDelayed({ activeJobId = null }, 4_000)
                    }
                } else if (ballView?.state !in setOf(FloatingBallState.Attention, FloatingBallState.Completed, FloatingBallState.Failed)) {
                    ballView?.post { ballView?.setState(FloatingBallState.Idle, 0) }
                }
            }
        }
    }

    private fun mapState(job: JobEntity): FloatingBallState = when {
        job.status == "completed" -> FloatingBallState.Completed
        job.status == "failed" || job.status == "cancelled" -> FloatingBallState.Failed
        job.status == "queued" -> FloatingBallState.Queued
        job.progress < 35 -> FloatingBallState.Resolving
        job.progress < 82 -> FloatingBallState.Searching
        else -> FloatingBallState.Finishing
    }

    private fun openApp(jobId: String?) {
        startActivity(Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            jobId?.let { putExtra("job_id", it) }
        })
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
    }
}

private class FloatingBallView(context: Context) : View(context) {
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
        state = value
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
        val center = width / 2f
        val radius = width.coerceAtMost(height) * .43f
        paint.style = Paint.Style.FILL
        paint.color = Color.WHITE
        paint.setShadowLayer(12f, 0f, 4f, 0x35000000)
        setLayerType(LAYER_TYPE_SOFTWARE, paint)
        canvas.drawCircle(center, height / 2f, radius, paint)
        paint.clearShadowLayer()

        clipPath.reset()
        clipPath.addCircle(center, height / 2f, radius - 4f, Path.Direction.CW)
        canvas.save()
        canvas.clipPath(clipPath)
        canvas.drawBitmap(logo, Rect(0, 0, logo.width, logo.height), RectF(center - radius, height / 2f - radius, center + radius, height / 2f + radius), paint)
        canvas.restore()

        val ringColor = when (state) {
            FloatingBallState.Attention, FloatingBallState.Failed -> 0xFFFF5A1F.toInt()
            FloatingBallState.Completed -> 0xFF25A75A.toInt()
            FloatingBallState.Idle -> 0xFF201713.toInt()
            else -> 0xFFFF5A1F.toInt()
        }
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = width * .065f
        paint.strokeCap = Paint.Cap.ROUND
        paint.color = if (state == FloatingBallState.Idle) 0x33201713 else 0x33FF5A1F
        ringRect.set(center - radius, height / 2f - radius, center + radius, height / 2f + radius)
        canvas.drawArc(ringRect, -90f, 360f, false, paint)
        paint.color = ringColor
        val sweep = when (state) {
            FloatingBallState.Idle -> 0f
            FloatingBallState.Attention, FloatingBallState.Failed -> 360f
            else -> 360f * displayedProgress / 100f
        }
        canvas.drawArc(ringRect, -90f, sweep, false, paint)
    }

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
