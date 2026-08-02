package com.mimotrust.xiaozhen.ui

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.PickVisualMediaRequest
import androidx.compose.foundation.Image
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.GenericShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mimotrust.xiaozhen.R
import com.mimotrust.xiaozhen.data.local.JobEntity
import com.mimotrust.xiaozhen.overlay.FloatingBallManager
import com.composables.icons.lucide.*
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.max
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

private enum class MainTab { Chat, History, Settings }

private val AppIconContinuousCorner = GenericShape { size, _ ->
    val width = size.width
    val height = size.height
    moveTo(width * .5f, 0f)
    cubicTo(width * .76f, 0f, width * .84f, 0f, width * .92f, height * .08f)
    cubicTo(width, height * .16f, width, height * .24f, width, height * .5f)
    cubicTo(width, height * .76f, width, height * .84f, width * .92f, height * .92f)
    cubicTo(width * .84f, height, width * .76f, height, width * .5f, height)
    cubicTo(width * .24f, height, width * .16f, height, width * .08f, height * .92f)
    cubicTo(0f, height * .84f, 0f, height * .76f, 0f, height * .5f)
    cubicTo(0f, height * .24f, 0f, height * .16f, width * .08f, height * .08f)
    cubicTo(width * .16f, 0f, width * .24f, 0f, width * .5f, 0f)
    close()
}

@Composable
fun MimoTrustApp(viewModel: MainViewModel, initialJobId: String?) {
    MimoTheme {
        val jobs by viewModel.jobs.collectAsStateWithLifecycle()
        var selectedTab by remember { mutableStateOf(if (initialJobId == null) MainTab.Chat else MainTab.History) }
        var selectedId by remember { mutableStateOf(initialJobId) }
        val selected = jobs.firstOrNull { it.jobId == selectedId }

        if (selected != null) {
            JobDetail(selected) { selectedId = null }
            return@MimoTheme
        }

        Scaffold(
            containerColor = Paper,
            bottomBar = { BottomNavigation(selectedTab) { selectedTab = it } },
        ) { scaffoldPadding ->
            when (selectedTab) {
                MainTab.Chat -> ChatScreen(
                    jobs = jobs,
                    onVerify = viewModel::verify,
                    onOpen = { selectedId = it.jobId },
                    modifier = Modifier.padding(scaffoldPadding),
                )
                MainTab.History -> HistoryScreen(
                    jobs = jobs,
                    onOpen = { selectedId = it.jobId },
                    modifier = Modifier.padding(scaffoldPadding),
                )
                MainTab.Settings -> SettingsScreen(Modifier.padding(scaffoldPadding))
            }
        }
    }
}

@Composable
private fun ChatScreen(
    jobs: List<JobEntity>,
    onVerify: (String, String) -> Unit,
    onOpen: (JobEntity) -> Unit,
    modifier: Modifier = Modifier,
) {
    var input by remember { mutableStateOf("") }
    var photo by remember { mutableStateOf<Bitmap?>(null) }
    var verificationMode by remember { mutableStateOf("speed") }
    var videoUri by remember { mutableStateOf<Uri?>(null) }
    val context = LocalContext.current
    val speechLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { input = it }
        }
    }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()) { bitmap ->
        photo = bitmap
    }
    val videoPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        videoUri = uri
    }
    val send = {
        if (input.isNotBlank()) {
            onVerify(input.trim(), verificationMode)
            input = ""
            photo = null
            videoUri = null
        }
    }

    Box(modifier.fillMaxSize().background(Paper)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 22.dp, top = 82.dp, end = 22.dp, bottom = 90.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Hi，今天想核实什么？", fontSize = 29.sp, lineHeight = 36.sp, fontWeight = FontWeight.Black, color = Ink)
                    Text("发来链接或告诉我你看到的内容", fontSize = 14.sp, color = Muted)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = verificationMode == "speed",
                            onClick = { verificationMode = "speed" },
                            label = { Text("快速") },
                        )
                        FilterChip(
                            selected = verificationMode == "quality",
                            onClick = { verificationMode = "quality" },
                            label = { Text("高质量") },
                        )
                    }
                }
            }
            if (jobs.isEmpty()) {
                item { StartPrompt { input = it } }
            } else {
                items(jobs.take(3).reversed(), key = { it.jobId }) {
                    ConversationTurn(it, onOpen)
                }
            }
        }

        BrandHeader(
            Modifier.align(Alignment.TopCenter).fillMaxWidth().background(Paper)
                .padding(start = 22.dp, top = 8.dp, end = 22.dp, bottom = 6.dp),
        )

        ChatComposer(
            value = input,
            onValueChange = { input = it },
            photo = photo,
            videoUri = videoUri,
            onClearPhoto = { photo = null },
            onClearVideo = { videoUri = null },
            onCamera = { cameraLauncher.launch(null) },
            onPickVideo = { videoPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.VideoOnly)) },
            onVoice = {
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.SIMPLIFIED_CHINESE.toLanguageTag())
                    putExtra(RecognizerIntent.EXTRA_PROMPT, "请说出需要核实的内容")
                }
                runCatching { speechLauncher.launch(intent) }
            },
            onSend = send,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

@Composable
private fun BrandHeader(modifier: Modifier = Modifier) {
    var muted by remember { mutableStateOf(false) }
    Box(modifier.height(56.dp), contentAlignment = Alignment.Center) {
        Image(
            painter = painterResource(R.drawable.xiaozhen_logo),
            contentDescription = "小真",
            modifier = Modifier.align(Alignment.CenterStart).size(44.dp).clip(AppIconContinuousCorner),
            contentScale = ContentScale.Crop,
        )
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("小真", fontSize = 16.sp, color = Ink)
            Text("MimoTrust 的专业核验助手", fontSize = 11.sp, color = LightMuted)
        }
        IconButton(
            onClick = { muted = !muted },
            modifier = Modifier.align(Alignment.CenterEnd).size(44.dp),
        ) {
            Icon(
                if (muted) Lucide.VolumeX else Lucide.Volume2,
                if (muted) "开启声音" else "静音",
                tint = Cocoa,
                modifier = Modifier.size(21.dp),
            )
        }
    }
}

@Composable
private fun StartPrompt(onPick: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(11.dp)) {
        Text("你可以这样问", color = Muted, fontSize = 13.sp)
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Color.White)
                .padding(horizontal = 16.dp, vertical = 4.dp),
        ) {
        listOf(
            "这个视频里说的是真的吗？",
            "帮我核实这条新闻的来源",
            "这段网传消息可信吗？",
        ).forEachIndexed { index, prompt ->
            Row(
                modifier = Modifier.fillMaxWidth().clickable { onPick(prompt) }.padding(vertical = 17.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Lucide.Link, null, tint = listOf(Blue, Green, Cyan)[index], modifier = Modifier.size(21.dp))
                Spacer(Modifier.width(12.dp))
                Text(prompt, color = Ink)
                Spacer(Modifier.weight(1f))
                Icon(Lucide.ChevronRight, null, tint = LightMuted, modifier = Modifier.size(20.dp))
            }
            if (index < 2) HorizontalDivider(color = Divider, modifier = Modifier.padding(start = 33.dp))
        }
        }
    }
}

@Composable
private fun ChatComposer(
    value: String,
    onValueChange: (String) -> Unit,
    photo: Bitmap?,
    videoUri: Uri?,
    onClearPhoto: () -> Unit,
    onClearVideo: () -> Unit,
    onCamera: () -> Unit,
    onPickVideo: () -> Unit,
    onVoice: () -> Unit,
    onSend: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth().imePadding()
            .padding(start = 16.dp, end = 16.dp, top = 6.dp, bottom = 4.dp),
    ) {
        if (photo != null) {
            Row(
                Modifier.padding(start = 12.dp, bottom = 8.dp).clip(RoundedCornerShape(16.dp)).background(SurfaceSoft)
                    .clickable(onClick = onClearPhoto).padding(6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Image(photo.asImageBitmap(), "待核实照片", Modifier.size(42.dp).clip(RoundedCornerShape(11.dp)), contentScale = ContentScale.Crop)
                Spacer(Modifier.width(8.dp))
                Text("已添加照片 · 点击移除", fontSize = 12.sp, color = Muted)
                Spacer(Modifier.width(8.dp))
            }
        }
        if (videoUri != null) {
            Row(
                Modifier.padding(start = 12.dp, bottom = 8.dp).clip(RoundedCornerShape(16.dp)).background(Color.White)
                    .clickable(onClick = onClearVideo).padding(horizontal = 10.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Lucide.Video, null, tint = Cocoa, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text("已选择相册视频 · 点击移除", fontSize = 12.sp, color = Muted)
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(32.dp))
                .background(Color.White).padding(horizontal = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onCamera, modifier = Modifier.size(48.dp)) { Icon(Lucide.Camera, "拍照", tint = Cocoa, modifier = Modifier.size(21.dp)) }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f).height(48.dp),
                singleLine = true,
                textStyle = TextStyle(color = Ink, fontSize = 14.sp),
                cursorBrush = SolidColor(Cocoa),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { onSend() }),
                decorationBox = { innerTextField ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.CenterStart) {
                        if (value.isEmpty()) Text("发消息或按住说话…", color = LightMuted, fontSize = 14.sp)
                        innerTextField()
                    }
                },
            )
            IconButton(onClick = onVoice, modifier = Modifier.size(48.dp)) {
                Icon(Lucide.AudioLines, "语音输入", tint = Cocoa, modifier = Modifier.size(21.dp))
            }
            IconButton(onClick = onPickVideo, modifier = Modifier.size(48.dp)) {
                Icon(Lucide.Plus, "从相册选择视频", tint = Cocoa, modifier = Modifier.size(24.dp))
            }
        }
    }
}

@Composable
private fun ConversationTurn(job: JobEntity, onOpen: (JobEntity) -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.End) {
            Box(
                Modifier.widthIn(max = 300.dp).clip(
                    RoundedCornerShape(topStart = 22.dp, topEnd = 8.dp, bottomStart = 22.dp, bottomEnd = 22.dp),
                ).background(Cocoa).padding(horizontal = 16.dp, vertical = 12.dp),
            ) {
                Text(job.sourceText, color = Color.White, fontSize = 14.sp, lineHeight = 20.sp, maxLines = 5, overflow = TextOverflow.Ellipsis)
            }
            Spacer(Modifier.height(5.dp))
            Text(formatMessageTime(job.createdAt), color = LightMuted, fontSize = 10.sp)
        }

        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.Start) {
            Box(Modifier.clickable { onOpen(job) }) { AssistantResultBubble(job) }
            Spacer(Modifier.height(5.dp))
            Text(formatMessageTime(job.createdAt, job.elapsedMs), color = LightMuted, fontSize = 10.sp)
        }
    }
}

@Composable
private fun AssistantResultBubble(job: JobEntity) {
    val active = job.status == "queued" || job.status == "running"
    val failed = job.status == "failed" || job.status == "cancelled"
    val visibleElapsed = rememberVisibleElapsed(job)
    Column(
        Modifier.fillMaxWidth().clip(
            RoundedCornerShape(topStart = 8.dp, topEnd = 24.dp, bottomStart = 24.dp, bottomEnd = 24.dp),
        ).background(Color.White).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            when {
                active -> CircularProgressIndicator(Modifier.size(18.dp), color = Orange, strokeWidth = 2.dp)
                failed -> Icon(Lucide.CircleAlert, null, tint = Orange, modifier = Modifier.size(19.dp))
                else -> Icon(Lucide.CircleCheck, null, tint = Green, modifier = Modifier.size(19.dp))
            }
            Spacer(Modifier.width(8.dp))
            Text(
                when {
                    active -> "正在为你核实"
                    failed -> "本次核实未完成"
                    else -> "核实结果已生成"
                },
                color = Ink,
                fontSize = 14.sp,
            )
            Spacer(Modifier.weight(1f))
            Text(formatElapsed(visibleElapsed), color = LightMuted, fontSize = 11.sp)
        }

        Box(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp))
                .background(if (active) Soft else OrangeSoft).padding(14.dp),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
                Text(
                    when {
                        active -> processLabel(job.progress)
                        failed -> "暂时无法得出结果"
                        else -> job.verdict ?: "核实完成"
                    },
                    color = if (active) Cocoa else Orange,
                    fontSize = 13.sp,
                )
                Text(
                    job.headline ?: job.sourceText,
                    color = Ink,
                    fontSize = 17.sp,
                    lineHeight = 23.sp,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                )
                val summary = if (active) job.displayText else job.conclusion
                if (!summary.isNullOrBlank()) {
                    Text(summary, color = Muted, fontSize = 13.sp, lineHeight = 19.sp, maxLines = 4, overflow = TextOverflow.Ellipsis)
                }
                if (!active && !job.sharingAdvice.isNullOrBlank()) {
                    Text(
                        "传播建议 · ${job.sharingAdvice}",
                        color = Cocoa,
                        fontSize = 12.sp,
                        lineHeight = 18.sp,
                    )
                }
                if (active) {
                    LinearProgressIndicator(
                        progress = { job.progress.coerceIn(0, 100) / 100f },
                        modifier = Modifier.fillMaxWidth().padding(top = 3.dp).height(4.dp).clip(CircleShape),
                        color = Orange,
                        trackColor = Divider,
                    )
                    Text("${job.progress}%", color = Muted, fontSize = 11.sp, modifier = Modifier.align(Alignment.End))
                }
            }
        }

        Text("处理过程", color = Muted, fontSize = 12.sp)
        InlineProcess(job.progress)

        if (!active && !failed) {
            HorizontalDivider(color = Divider)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("公开证据 ${job.evidenceCount} 条", color = Muted, fontSize = 11.sp)
                Text(formatCreatedAt(job.createdAt), color = LightMuted, fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun InlineProcess(progress: Int) {
    val stages = listOf(
        "读取内容" to 8,
        "理解文字与画面" to 22,
        "提取核心主张" to 42,
        "规划核验" to 54,
        "检索公开来源" to 66,
        "归一化证据" to 72,
        "筛选证据关系" to 81,
        "综合研判" to 90,
        "生成完整报告" to 100,
    )
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        stages.forEachIndexed { index, (label, threshold) ->
            val completed = progress >= threshold
            val previousThreshold = stages.getOrNull(index - 1)?.second ?: 0
            val current = !completed && progress >= previousThreshold
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(8.dp).clip(CircleShape).background(
                        when {
                            completed && !current -> Green
                            current -> Orange
                            else -> Divider
                        },
                    ),
                )
                Spacer(Modifier.width(10.dp))
                Text(label, color = if (completed) Ink else LightMuted, fontSize = 13.sp)
                if (current && progress < 100) {
                    Spacer(Modifier.weight(1f))
                    Text("进行中", color = Orange, fontSize = 11.sp)
                }
            }
        }
    }
}

@Composable
private fun JobCard(job: JobEntity, onOpen: (JobEntity) -> Unit) {
    val active = job.status == "queued" || job.status == "running"
    val failed = job.status == "failed" || job.status == "cancelled"
    val visibleElapsed = rememberVisibleElapsed(job)
    Card(
        modifier = Modifier.fillMaxWidth().clickable { onOpen(job) },
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(0.dp),
    ) {
        Column(Modifier.padding(19.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(38.dp).clip(CircleShape).background(if (active) Color.White else Color.White),
                    contentAlignment = Alignment.Center,
                ) {
                    when {
                        active -> CircularProgressIndicator(Modifier.size(18.dp), color = Orange, strokeWidth = 2.dp)
                        failed -> Icon(Lucide.CircleAlert, null, tint = Orange, modifier = Modifier.size(20.dp))
                        else -> Icon(Lucide.CircleCheck, null, tint = Ink, modifier = Modifier.size(20.dp))
                    }
                }
                Spacer(Modifier.width(11.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        when { active -> "小真正在核实"; failed -> "核实未完成"; else -> job.verdict ?: "核实完成" },
                        color = Ink,
                    )
                    Text(
                        if (active) job.displayText else formatCreatedAt(job.createdAt),
                        color = Muted,
                        fontSize = 12.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(formatElapsed(visibleElapsed), color = Muted, fontSize = 11.sp)
            }
            Text(
                job.headline ?: job.sourceText,
                color = Ink,
                fontSize = 17.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (active) {
                LinearProgressIndicator(
                    progress = { job.progress.coerceIn(0, 100) / 100f },
                    modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
                    color = Orange,
                    trackColor = Divider,
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(processLabel(job.progress), color = Muted, fontSize = 12.sp)
                    Text("${job.progress}%", color = Muted, fontSize = 12.sp)
                }
            } else if (!job.conclusion.isNullOrBlank()) {
                Text(job.conclusion, color = Muted, fontSize = 13.sp, lineHeight = 19.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun HistoryScreen(jobs: List<JobEntity>, onOpen: (JobEntity) -> Unit, modifier: Modifier = Modifier) {
    LazyColumn(
        modifier.fillMaxSize().background(Paper),
        contentPadding = PaddingValues(22.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Box(Modifier.fillMaxWidth().padding(bottom = 10.dp), contentAlignment = Alignment.Center) {
                Text("核实记录", fontSize = 18.sp, color = Ink, fontWeight = FontWeight.Bold)
            }
        }
        if (jobs.isEmpty()) item { EmptyHistory() }
        items(jobs, key = { it.jobId }) { JobCard(it, onOpen) }
    }
}

@Composable
private fun EmptyHistory() {
    Column(
        Modifier.fillMaxWidth().padding(top = 92.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.size(64.dp).clip(CircleShape).background(SurfaceSoft), contentAlignment = Alignment.Center) {
            Icon(Lucide.History, null, tint = LightMuted, modifier = Modifier.size(28.dp))
        }
        Spacer(Modifier.height(15.dp))
        Text("还没有核实记录", color = Ink)
        Text("去对话页发送第一条链接吧", color = Muted, fontSize = 13.sp)
    }
}

@Composable
private fun SettingsScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var notifications by remember { mutableStateOf(true) }
    var darkMode by remember { mutableStateOf(false) }
    var floatingBall by remember { mutableStateOf(FloatingBallManager.isEnabled(context) && FloatingBallManager.canDraw(context)) }
    val overlayPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        floatingBall = FloatingBallManager.canDraw(context)
        if (floatingBall) FloatingBallManager.enable(context)
    }
    LazyColumn(
        modifier.fillMaxSize().background(Paper),
        contentPadding = PaddingValues(22.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Box(Modifier.fillMaxWidth().padding(bottom = 8.dp), contentAlignment = Alignment.Center) {
                Text("设置", fontSize = 18.sp, color = Ink, fontWeight = FontWeight.Bold)
            }
        }
        item {
            SettingsGroup {
                SettingsToggle(Lucide.MessageCircle, "悬浮核验球", "刷视频时常驻，点击即可发起核验", floatingBall) { enabled ->
                    if (!enabled) {
                        FloatingBallManager.disable(context)
                        floatingBall = false
                    } else if (FloatingBallManager.canDraw(context)) {
                        FloatingBallManager.enable(context)
                        floatingBall = true
                    } else {
                        overlayPermissionLauncher.launch(FloatingBallManager.permissionIntent(context))
                    }
                }
                HorizontalDivider(color = Divider, modifier = Modifier.padding(start = 54.dp))
                SettingsToggle(Lucide.Bell, "核实完成提醒", "结果生成后及时通知", notifications) { notifications = it }
                HorizontalDivider(color = Divider, modifier = Modifier.padding(start = 54.dp))
                SettingsToggle(Lucide.Moon, "深色模式", "即将支持", darkMode, enabled = false) { darkMode = it }
            }
        }
        item {
            SettingsGroup {
                SettingsLink(Lucide.Shield, "隐私与数据", "核实记录仅保存在你的设备")
                HorizontalDivider(color = Divider, modifier = Modifier.padding(start = 54.dp))
                SettingsLink(Lucide.Info, "关于小真", "版本 0.1.0")
            }
        }
        item {
            Text(
                "AI 辅助核验仅供信息参考，请结合原始来源与完整语境判断。",
                color = LightMuted,
                fontSize = 12.sp,
                lineHeight = 18.sp,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
            )
        }
    }
}

@Composable
private fun SettingsGroup(content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Color.White).padding(horizontal = 16.dp)) { content() }
}

@Composable
private fun SettingsToggle(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    checked: Boolean,
    enabled: Boolean = true,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = if (enabled) Green else LightMuted, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(16.dp))
        Text(title, color = if (enabled) Ink else LightMuted, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onCheckedChange, enabled = enabled)
    }
}

@Composable
private fun SettingsLink(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, subtitle: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Blue, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(16.dp))
        Text(title, color = Ink, modifier = Modifier.weight(1f))
        Icon(Lucide.ChevronRight, null, tint = LightMuted, modifier = Modifier.size(20.dp))
    }
}

@Composable
private fun BottomNavigation(selected: MainTab, onSelect: (MainTab) -> Unit) {
    Column(Modifier.fillMaxWidth().background(Paper)) {
        if (selected != MainTab.Chat) HorizontalDivider(color = Divider, thickness = 0.5.dp)
        Row(
            Modifier.fillMaxWidth().height(74.dp).padding(horizontal = 42.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            NavigationItem(MainTab.Chat, selected, "问小真", onSelect)
            NavigationItem(MainTab.History, selected, "历史", onSelect)
            NavigationItem(MainTab.Settings, selected, "设置", onSelect)
        }
    }
}

@Composable
private fun NavigationItem(
    tab: MainTab,
    selected: MainTab,
    label: String,
    onSelect: (MainTab) -> Unit,
) {
    val active = tab == selected
    Column(
        Modifier.width(72.dp).clip(RoundedCornerShape(16.dp)).clickable { onSelect(tab) }.padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        when (tab) {
            MainTab.Chat -> ChatTabIcon(active, label)
            MainTab.History -> HistoryTabIcon(active, label)
            MainTab.Settings -> SettingsTabIcon(active, label)
        }
        Spacer(Modifier.height(3.dp))
        Text(label, color = if (active) Cocoa else LightMuted, fontSize = 11.sp)
    }
}

@Composable
private fun ChatTabIcon(active: Boolean, contentDescription: String) {
    Box(
        Modifier.size(30.dp).semantics { this.contentDescription = contentDescription },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(30.dp)) {
            scale(0.75f, pivot = Offset(size.width / 2f, size.height / 2f)) {
            val bubblePath = Path().apply {
                moveTo(15.dp.toPx(), 2.dp.toPx())
                cubicTo(22.dp.toPx(), 2.dp.toPx(), 27.dp.toPx(), 6.8.dp.toPx(), 27.dp.toPx(), 13.dp.toPx())
                cubicTo(27.dp.toPx(), 19.2.dp.toPx(), 22.dp.toPx(), 24.dp.toPx(), 15.dp.toPx(), 24.dp.toPx())
                lineTo(12.dp.toPx(), 24.dp.toPx())
                lineTo(6.dp.toPx(), 28.dp.toPx())
                lineTo(8.dp.toPx(), 22.dp.toPx())
                cubicTo(4.8.dp.toPx(), 19.8.dp.toPx(), 3.dp.toPx(), 16.5.dp.toPx(), 3.dp.toPx(), 13.dp.toPx())
                cubicTo(3.dp.toPx(), 6.8.dp.toPx(), 8.dp.toPx(), 2.dp.toPx(), 15.dp.toPx(), 2.dp.toPx())
                close()
            }
            if (active) drawPath(path = bubblePath, color = Cocoa, style = Fill)
            drawPath(
                path = bubblePath,
                color = if (active) Cocoa else LightMuted,
                style = Stroke(width = 1.7.dp.toPx()),
            )
            listOf(11.dp, 15.dp, 19.dp).forEach { x ->
                drawCircle(
                    color = if (active) Color.White else LightMuted,
                    radius = 1.15.dp.toPx(),
                    center = Offset(x.toPx(), 13.dp.toPx()),
                )
            }
            }
        }
    }
}

@Composable
private fun HistoryTabIcon(active: Boolean, contentDescription: String) {
    Canvas(
        Modifier.size(30.dp).semantics { this.contentDescription = contentDescription },
    ) {
        scale(0.75f, pivot = Offset(size.width / 2f, size.height / 2f)) {
        val center = Offset(size.width / 2f, size.height / 2f)
        val bodyColor = if (active) Cocoa else LightMuted
        if (active) drawCircle(color = bodyColor, radius = 11.5.dp.toPx(), center = center, style = Fill)
        drawCircle(
            color = bodyColor,
            radius = 11.5.dp.toPx(),
            center = center,
            style = Stroke(width = 1.7.dp.toPx()),
        )
        val detailColor = if (active) Color.White else LightMuted
        drawLine(
            color = detailColor,
            start = center,
            end = Offset(center.x, center.y - 6.dp.toPx()),
            strokeWidth = 1.7.dp.toPx(),
            cap = StrokeCap.Round,
        )
        drawLine(
            color = detailColor,
            start = center,
            end = Offset(center.x + 5.dp.toPx(), center.y + 3.dp.toPx()),
            strokeWidth = 1.7.dp.toPx(),
            cap = StrokeCap.Round,
        )
        drawCircle(detailColor, radius = 1.25.dp.toPx(), center = center)
        }
    }
}

@Composable
private fun SettingsTabIcon(active: Boolean, contentDescription: String) {
    Canvas(
        Modifier.size(30.dp).semantics { this.contentDescription = contentDescription },
    ) {
        scale(0.75f, pivot = Offset(size.width / 2f, size.height / 2f)) {
        val center = Offset(size.width / 2f, size.height / 2f)
        val outerRadius = 12.5.dp.toPx()
        val rootRadius = 9.4.dp.toPx()
        val gearPath = Path()
        repeat(32) { index ->
            val angle = -PI / 2 + index * (2 * PI / 32)
            val radius = if (index % 4 == 1 || index % 4 == 2) outerRadius else rootRadius
            val x = center.x + (cos(angle) * radius).toFloat()
            val y = center.y + (sin(angle) * radius).toFloat()
            if (index == 0) gearPath.moveTo(x, y) else gearPath.lineTo(x, y)
        }
        gearPath.close()
        if (active) drawPath(path = gearPath, color = Cocoa, style = Fill)
        drawPath(
            path = gearPath,
            color = if (active) Cocoa else LightMuted,
            style = Stroke(width = 1.7.dp.toPx()),
        )
        drawCircle(
            color = if (active) Color.White else LightMuted,
            radius = 3.4.dp.toPx(),
            center = center,
            style = if (active) Fill else Stroke(width = 1.7.dp.toPx()),
        )
        }
    }
}

@Composable
private fun JobDetail(job: JobEntity, onBack: () -> Unit) {
    val active = job.status == "queued" || job.status == "running"
    val visibleElapsed = rememberVisibleElapsed(job)
    Scaffold(containerColor = Paper) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(22.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    IconButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterStart)) {
                        Icon(Lucide.ArrowLeft, "返回")
                    }
                    Text("核实详情", fontSize = 18.sp, color = Ink, fontWeight = FontWeight.Bold)
                }
            }
            item {
                Card(shape = RoundedCornerShape(28.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                    Column(Modifier.padding(23.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(job.verdict ?: if (active) "核实进行中" else "核实未完成", color = Orange, fontSize = 13.sp)
                        Text(job.headline ?: job.sourceText, color = Ink, fontSize = 23.sp, lineHeight = 31.sp)
                        Text(job.conclusion ?: job.displayText, color = Muted, lineHeight = 21.sp)
                        HorizontalDivider(color = Divider)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Metric("公开证据", "${job.evidenceCount} 条")
                            Metric("分析用时", formatElapsed(visibleElapsed))
                            Metric("流程进度", "${job.progress}%")
                        }
                    }
                }
            }
            job.claimDetails?.let { item { DetailSection("逐主张核验", it) } }
            job.sharingAdvice?.let { item { DetailSection("传播建议", it) } }
            job.narrativeAnalysis?.let { item { DetailSection("叙事分析", it) } }
            job.evidenceGaps?.let { item { DetailSection("待补证据", it) } }
            job.uncertaintyNote?.let { item { DetailSection("主要不确定性", it) } }
            job.keyEvidence?.let { item { DetailSection("关键依据", it) } }
            item { Timeline(job) }
            item {
                Text(
                    job.aiDisclaimer ?: "AI 辅助核验，仅供信息参考。请结合原始来源与完整语境判断。",
                    color = Muted,
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                )
            }
        }
    }
}

@Composable
private fun DetailSection(title: String, content: String) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(title, fontWeight = FontWeight.Black, fontSize = 19.sp)
            Text(content, color = Muted, lineHeight = 21.sp)
        }
    }
}

@Composable
private fun Timeline(job: JobEntity) {
    val stages = listOf(
        "读取链接与内容" to 8,
        "理解文字与画面" to 22,
        "提取核心主张" to 42,
        "整理并编号主张" to 46,
        "规划核验与检索" to 54,
        "并发检索公开来源" to 66,
        "归一化候选证据" to 72,
        "筛选证据关系" to 81,
        "综合研判主张" to 90,
        "生成完整报告" to 100,
    )
    Card(shape = RoundedCornerShape(26.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.padding(22.dp)) {
            Text("核实过程", fontSize = 19.sp, color = Ink)
            Spacer(Modifier.height(18.dp))
            stages.forEachIndexed { index, (label, threshold) ->
                Row(verticalAlignment = Alignment.Top) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(18.dp).clip(CircleShape).background(if (job.progress >= threshold) Orange else Divider))
                        if (index < stages.lastIndex) Box(Modifier.width(2.dp).height(34.dp).background(if (job.progress >= stages[index + 1].second) Orange else Divider))
                    }
                    Spacer(Modifier.width(14.dp))
                    Column {
                        Text(label, color = if (job.progress >= threshold) Ink else Muted)
                        if (job.progress in threshold until (stages.getOrNull(index + 1)?.second ?: 101)) Text("正在处理…", color = Orange, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun Metric(label: String, value: String) {
    Column { Text(value, color = Ink); Text(label, color = LightMuted, fontSize = 11.sp) }
}

private fun processLabel(progress: Int): String = when (progress) {
    in 0..12 -> "正在读取链接"
    in 13..35 -> "正在理解文字与画面"
    in 36..49 -> "正在整理待核实主张"
    in 50..59 -> "正在规划检索"
    in 60..74 -> "正在检索并归一化来源"
    in 75..86 -> "正在筛选证据关系"
    in 87..94 -> "正在综合研判"
    else -> "正在生成完整报告"
}

private fun formatCreatedAt(value: String): String = runCatching {
    Instant.parse(value).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("MM月dd日 HH:mm"))
}.getOrDefault("最近核实")

private fun formatMessageTime(value: String, offsetMilliseconds: Long = 0): String = runCatching {
    Instant.parse(value).plusMillis(offsetMilliseconds).atZone(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("HH:mm"))
}.getOrDefault("")

private fun formatElapsed(milliseconds: Long): String {
    val seconds = milliseconds / 1000
    return if (seconds < 60) "${seconds}s" else "${seconds / 60}m ${seconds % 60}s"
}

@Composable
private fun rememberVisibleElapsed(job: JobEntity): Long {
    val active = job.status == "queued" || job.status == "running"
    var now by remember(job.jobId) { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(job.jobId, active) {
        while (active) {
            now = System.currentTimeMillis()
            delay(1_000)
        }
    }
    if (!active) return job.elapsedMs
    val createdAt = runCatching { Instant.parse(job.createdAt).toEpochMilli() }.getOrNull() ?: return job.elapsedMs
    return max(job.elapsedMs, now - createdAt)
}
