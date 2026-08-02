package com.mimotrust.xiaozhen.ui

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.PickVisualMediaRequest
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.foundation.Image
import androidx.compose.foundation.Canvas
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.GenericShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.zIndex
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.drawBehind
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mimotrust.xiaozhen.R
import com.mimotrust.xiaozhen.data.local.JobEntity
import com.mimotrust.xiaozhen.data.remote.VerificationDetailsDto
import com.mimotrust.xiaozhen.data.remote.ClaimCheckDto
import com.mimotrust.xiaozhen.data.remote.EvidenceDto
import com.mimotrust.xiaozhen.data.remote.JobEventPayloadDto
import com.mimotrust.xiaozhen.overlay.FloatingBallManager
import com.composables.icons.lucide.*
import com.google.gson.Gson
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.net.URI
import java.util.Locale
import kotlin.math.max
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.roundToInt

private enum class MainTab { Chat, History, Settings }
private val BottomBarHeight = 68.dp

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
        val chatListState = rememberLazyListState()
        val historyListState = rememberLazyListState()
        val settingsListState = rememberLazyListState()
        val selected = jobs.firstOrNull { it.jobId == selectedId }
        val density = LocalDensity.current
        val imeBottom = with(density) { WindowInsets.ime.getBottom(this).toDp() }
        val composerBottomInset = maxOf(0.dp, BottomBarHeight - imeBottom)

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
                    listState = chatListState,
                    composerBottomInset = composerBottomInset,
                    modifier = Modifier.padding(top = scaffoldPadding.calculateTopPadding()),
                )
                MainTab.History -> HistoryScreen(
                    jobs = jobs,
                    onOpen = { selectedId = it.jobId },
                    listState = historyListState,
                    modifier = Modifier.padding(scaffoldPadding),
                )
                MainTab.Settings -> SettingsScreen(
                    listState = settingsListState,
                    modifier = Modifier.padding(scaffoldPadding),
                )
            }
        }
    }
}

@Composable
private fun ChatScreen(
    jobs: List<JobEntity>,
    onVerify: (String, String) -> Unit,
    onOpen: (JobEntity) -> Unit,
    listState: LazyListState,
    composerBottomInset: Dp,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val preferences = remember(context) {
        context.getSharedPreferences("mimo-ui", Context.MODE_PRIVATE)
    }
    var input by remember { mutableStateOf("") }
    var photo by remember { mutableStateOf<Bitmap?>(null) }
    var verificationMode by remember {
        mutableStateOf(
            preferences.getString("verification-mode", "speed")
                ?.takeIf { it in setOf("speed", "quality") }
                ?: "speed"
        )
    }
    var videoUri by remember { mutableStateOf<Uri?>(null) }
    var waitingForNewMessage by remember { mutableStateOf(false) }
    var newestJobBeforeSend by remember { mutableStateOf<String?>(null) }
    val visibleJobs = jobs.take(3).reversed()
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
            newestJobBeforeSend = jobs.firstOrNull()?.jobId
            waitingForNewMessage = true
            onVerify(input.trim(), verificationMode)
            input = ""
            photo = null
            videoUri = null
        }
    }
    val activeJob = jobs.firstOrNull { it.status == "queued" || it.status == "running" }
    rememberFollowLatestListState(
        state = listState,
        contentKey = Triple(activeJob?.sequence, activeJob?.processArtifacts?.length, activeJob?.thinkingText?.length),
        enabled = activeJob != null,
    )

    LaunchedEffect(jobs.firstOrNull()?.jobId, waitingForNewMessage) {
        val newestJobId = jobs.firstOrNull()?.jobId
        if (waitingForNewMessage && newestJobId != null && newestJobId != newestJobBeforeSend) {
            // 欢迎卡占据索引 0，新消息从索引 1 开始。
            listState.animateScrollToItem(visibleJobs.size)
            waitingForNewMessage = false
        }
    }

    Box(modifier.fillMaxSize().background(Paper)) {
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 22.dp, top = 82.dp, end = 22.dp, bottom = 132.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            item { WelcomeHeroCard() }
            if (jobs.isEmpty()) {
                item { StartPrompt { input = it } }
            } else {
                items(visibleJobs, key = { it.jobId }) {
                    ConversationTurn(it, onOpen)
                }
            }
        }

        BrandHeader(
            Modifier.align(Alignment.TopCenter).fillMaxWidth().zIndex(3f).background(Paper)
                .padding(start = 22.dp, top = 8.dp, end = 22.dp, bottom = 6.dp),
        )

        Box(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(bottom = composerBottomInset).zIndex(2f),
            contentAlignment = Alignment.BottomCenter,
        ) {
            ChatComposer(
                value = input,
                onValueChange = { input = it },
                verificationMode = verificationMode,
                onVerificationModeChange = { mode ->
                    verificationMode = mode
                    preferences.edit().putString("verification-mode", mode).apply()
                },
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
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun BrandHeader(
    modifier: Modifier = Modifier,
) {
    var muted by remember { mutableStateOf(false) }
    Box(modifier.height(56.dp), contentAlignment = Alignment.Center) {
        Image(
            painter = painterResource(R.drawable.xiaozhen_logo),
            contentDescription = "小真",
            modifier = Modifier.align(Alignment.CenterStart).size(44.dp).clip(AppIconContinuousCorner),
            contentScale = ContentScale.Crop,
        )
        Column(
            Modifier.align(Alignment.Center).width(238.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(1.dp),
        ) {
            Text("小真", fontSize = 16.sp, color = Ink)
            Text("事实核验助手", fontSize = 11.sp, color = LightMuted)
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
private fun WelcomeHeroCard() {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(Color.White)
            .padding(start = 14.dp, top = 14.dp, end = 14.dp, bottom = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Image(
            painter = painterResource(R.drawable.xiaozhen_hero),
            contentDescription = "小真欢迎插画",
            modifier = Modifier.fillMaxWidth().height(230.dp).clip(RoundedCornerShape(22.dp)),
            contentScale = ContentScale.Fit,
        )
        Spacer(Modifier.height(14.dp))
        Text("Hi，今天想核实什么？", color = Ink, fontSize = 23.sp, lineHeight = 30.sp)
        Spacer(Modifier.height(5.dp))
        Text("发来链接或告诉我你看到的内容", color = LightMuted, fontSize = 13.sp)
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
    verificationMode: String,
    onVerificationModeChange: (String) -> Unit,
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
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("核验方式", color = LightMuted, fontSize = 11.sp)
            Spacer(Modifier.weight(1f))
            VerificationModeControl(verificationMode, onVerificationModeChange)
        }
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
    if (active) {
        Row(
            Modifier.fillMaxWidth().clip(
                RoundedCornerShape(topStart = 8.dp, topEnd = 22.dp, bottomStart = 22.dp, bottomEnd = 22.dp),
            ).background(Color.White).padding(horizontal = 15.dp, vertical = 13.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CircularProgressIndicator(Modifier.size(17.dp), color = Orange, strokeWidth = 2.dp)
            Spacer(Modifier.width(10.dp))
            Text(
                job.displayText,
                color = Ink,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(10.dp))
            Text(formatElapsed(visibleElapsed), color = LightMuted, fontSize = 11.sp)
        }
        return
    }
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

        SourceDetailsCard(job)
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
            }
        }
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
private fun SourceDetailsCard(job: JobEntity, compact: Boolean = false) {
    val metadata = job.extractedMetadata?.lineSequence()
        ?.mapNotNull { line ->
            val parts = line.split('｜', limit = 2)
            if (parts.size == 2 && parts[1].isNotBlank()) parts[0] to parts[1] else null
        }
        ?.toMap()
        .orEmpty()
    val source = remember(job.sourceText) { sourcePresentation(job.sourceText) }
    val title = metadata["标题"] ?: source.detail
    val platform = metadata["平台"] ?: source.label
    val topic = metadata["主题"]
    val iconSize = if (compact) 32.dp else 36.dp
    val sectionRadius = if (compact) 15.dp else 18.dp

    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(sectionRadius)).background(BlueSoft)
            .padding(horizontal = 14.dp, vertical = if (compact) 11.dp else 13.dp),
        verticalArrangement = Arrangement.spacedBy(if (compact) 9.dp else 11.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(iconSize).clip(RoundedCornerShape(11.dp)).background(Color.White),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    if (source.isVideo) Lucide.Video else Lucide.Link,
                    contentDescription = null,
                    tint = Blue,
                    modifier = Modifier.size(18.dp),
                )
            }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("信源详情", color = Ink, fontSize = 13.sp, lineHeight = 18.sp)
                Text(
                    platform,
                    color = Muted,
                    fontSize = 11.sp,
                    lineHeight = 15.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Text(
            title,
            color = Ink,
            fontSize = if (compact) 13.sp else 14.sp,
            lineHeight = if (compact) 18.sp else 20.sp,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(start = iconSize + 10.dp),
        )

        topic?.let {
            Row(
                Modifier.fillMaxWidth().padding(start = iconSize + 10.dp).clip(RoundedCornerShape(12.dp))
                    .background(Color.White.copy(alpha = .78f))
                    .padding(horizontal = 10.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Lucide.Hash, contentDescription = null, tint = Blue, modifier = Modifier.size(15.dp))
                Spacer(Modifier.width(6.dp))
                Text(
                    it,
                    color = Ink,
                    fontSize = 11.sp,
                    lineHeight = 17.sp,
                    maxLines = if (compact) 1 else 3,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun ResultSummaryCard(job: JobEntity, active: Boolean, failed: Boolean, progress: Float) {
    val tint = if (active) Amber else Orange
    val background = if (active) AmberSoft else OrangeSoft
    val status = when {
        active -> processLabel(job.progress)
        failed -> "暂时无法得出结果"
        else -> job.verdict ?: "核实完成"
    }
    val icon = when {
        active -> Lucide.Search
        failed -> Lucide.CircleAlert
        else -> Lucide.CircleCheck
    }
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(background).padding(14.dp),
        verticalAlignment = Alignment.Top,
    ) {
        ResultSectionIcon(icon, tint)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Text(status, color = tint, fontSize = 13.sp, lineHeight = 18.sp)
            Text(
                job.headline ?: job.sourceText,
                color = Ink,
                fontSize = 16.sp,
                lineHeight = 22.sp,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
            )
            val summary = if (active) job.displayText else job.conclusion
            if (!summary.isNullOrBlank()) {
                Text(summary, color = Muted, fontSize = 13.sp, lineHeight = 19.sp, maxLines = 4, overflow = TextOverflow.Ellipsis)
            }
            if (!active && !job.sharingAdvice.isNullOrBlank()) {
                Text("传播建议 · ${job.sharingAdvice}", color = Cocoa, fontSize = 12.sp, lineHeight = 18.sp)
            }
            if (active) {
                LinearProgressIndicator(
                    progress = { progress },
                    modifier = Modifier.fillMaxWidth().padding(top = 3.dp).height(4.dp).clip(CircleShape),
                    color = Amber,
                    trackColor = Divider,
                )
                Text("${(progress * 100).roundToInt()}%", color = Muted, fontSize = 11.sp, modifier = Modifier.align(Alignment.End))
            }
        }
    }
}

@Composable
private fun ProcessSectionCard(jobId: String, progress: Int, active: Boolean) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(GreenSoft).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        ResultSectionHeader(
            icon = Lucide.ListChecks,
            title = "处理过程",
            subtitle = if (active) processLabel(progress) else "核验流程记录",
            tint = Green,
        )
        InlineProcess(jobId, progress, active, Modifier.padding(start = 24.dp))
    }
}

@Composable
private fun ResultSectionHeader(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    tint: Color,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        ResultSectionIcon(icon, tint)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, color = Ink, fontSize = 13.sp, lineHeight = 18.sp)
            Text(subtitle, color = Muted, fontSize = 11.sp, lineHeight = 15.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun ResultSectionIcon(icon: androidx.compose.ui.graphics.vector.ImageVector, tint: Color) {
    Box(
        Modifier.size(36.dp).clip(RoundedCornerShape(11.dp)).background(Color.White.copy(alpha = .78f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
    }
}

@Composable
private fun InlineProcess(jobId: String, progress: Int, isRunning: Boolean, modifier: Modifier = Modifier) {
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
    val targetCount = stages.count { progress >= it.second }
    // 初次进入视图时直接采用当前真实阶段；只有任务仍在运行且收到后续事件时才增量展开。
    var revealedCount by remember(jobId) { mutableStateOf(targetCount) }
    LaunchedEffect(jobId, targetCount, isRunning) {
        if (!isRunning) {
            revealedCount = targetCount
        } else {
            while (revealedCount < targetCount) {
                revealedCount += 1
                delay(120)
            }
        }
    }

    Column(modifier) {
        stages.forEachIndexed { index, (label, threshold) ->
            val current = isRunning && index == targetCount - 1
            val completed = index < targetCount && !current
            AnimatedVisibility(
                visible = index < revealedCount,
                enter = fadeIn(tween(180)) + expandVertically(animationSpec = tween(220), expandFrom = Alignment.Top),
            ) {
                Row(Modifier.height(30.dp), verticalAlignment = Alignment.CenterVertically) {
                    Canvas(Modifier.width(12.dp).height(30.dp)) {
                        val centerX = size.width / 2f
                        val centerY = size.height / 2f
                        if (index > 0) drawLine(Green, Offset(centerX, 0f), Offset(centerX, centerY), strokeWidth = 1.dp.toPx())
                        if (index + 1 < revealedCount) {
                            drawLine(
                                if (completed) Green else Divider,
                                Offset(centerX, centerY),
                                Offset(centerX, size.height),
                                strokeWidth = 1.dp.toPx(),
                            )
                        }
                        drawCircle(if (completed) Green else Orange, radius = 4.dp.toPx(), center = Offset(centerX, centerY))
                    }
                    Spacer(Modifier.width(10.dp))
                    Text(label, color = Ink, fontSize = 13.sp, lineHeight = 18.sp)
                    if (current && progress < 100) {
                        Spacer(Modifier.weight(1f))
                        Text("进行中", color = Orange, fontSize = 11.sp)
                    }
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
    val continuousProgress by animateFloatAsState(
        targetValue = job.progress.coerceIn(0, 100) / 100f,
        animationSpec = tween(700),
        label = "history-progress-${job.jobId}",
    )
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
            SourceDetailsCard(job, compact = true)
            Text(
                job.headline ?: job.sourceText,
                color = Ink,
                fontSize = 17.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (active) {
                LinearProgressIndicator(
                    progress = { continuousProgress },
                    modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
                    color = Orange,
                    trackColor = Divider,
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(processLabel(job.progress), color = Muted, fontSize = 12.sp)
                    Text("${(continuousProgress * 100).roundToInt()}%", color = Muted, fontSize = 12.sp)
                }
            } else if (!job.conclusion.isNullOrBlank()) {
                Text(job.conclusion, color = Muted, fontSize = 13.sp, lineHeight = 19.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun HistoryScreen(
    jobs: List<JobEntity>,
    onOpen: (JobEntity) -> Unit,
    listState: LazyListState,
    modifier: Modifier = Modifier,
) {
    var query by rememberSaveable { mutableStateOf("") }
    val filteredJobs = remember(jobs, query) {
        val keyword = query.trim()
        if (keyword.isEmpty()) jobs else jobs.filter { job ->
            listOfNotNull(
                job.sourceText,
                job.headline,
                job.conclusion,
                job.verdict,
                job.displayText,
                job.extractedMetadata,
                sourcePresentation(job.sourceText).label,
            ).any { it.contains(keyword, ignoreCase = true) }
        }
    }
    LazyColumn(
        state = listState,
        modifier = modifier.fillMaxSize().background(Paper),
        contentPadding = PaddingValues(22.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Box(Modifier.fillMaxWidth().padding(bottom = 10.dp), contentAlignment = Alignment.Center) {
                Text("核实记录", fontSize = 18.sp, color = Ink, fontWeight = FontWeight.Bold)
            }
        }
        item {
            Row(
                Modifier.fillMaxWidth().height(46.dp).clip(RoundedCornerShape(23.dp))
                    .background(Color.White).padding(horizontal = 15.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Lucide.Search, contentDescription = null, tint = LightMuted, modifier = Modifier.size(19.dp))
                Spacer(Modifier.width(9.dp))
                BasicTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    textStyle = TextStyle(color = Ink, fontSize = 14.sp),
                    cursorBrush = SolidColor(Cocoa),
                    decorationBox = { innerTextField ->
                        Box(contentAlignment = Alignment.CenterStart) {
                            if (query.isEmpty()) Text("搜索标题、来源或核实内容", color = LightMuted, fontSize = 13.sp)
                            innerTextField()
                        }
                    },
                )
                if (query.isNotEmpty()) {
                    IconButton(onClick = { query = "" }, modifier = Modifier.size(32.dp)) {
                        Icon(Lucide.X, contentDescription = "清除搜索", tint = Muted, modifier = Modifier.size(17.dp))
                    }
                }
            }
        }
        when {
            jobs.isEmpty() -> item { EmptyHistory() }
            filteredJobs.isEmpty() -> item { EmptySearchResult(query) }
            else -> items(filteredJobs, key = { it.jobId }) { JobCard(it, onOpen) }
        }
    }
}

@Composable
private fun EmptySearchResult(query: String) {
    Column(
        Modifier.fillMaxWidth().padding(top = 72.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(Lucide.SearchX, contentDescription = null, tint = LightMuted, modifier = Modifier.size(30.dp))
        Spacer(Modifier.height(12.dp))
        Text("没有找到相关记录", color = Ink)
        Text("试试其他关键词 · $query", color = Muted, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
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
private fun SettingsScreen(listState: LazyListState, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var notifications by remember { mutableStateOf(true) }
    var darkMode by remember { mutableStateOf(false) }
    var floatingBall by remember { mutableStateOf(FloatingBallManager.isEnabled(context) && FloatingBallManager.canDraw(context)) }
    val overlayPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        floatingBall = FloatingBallManager.canDraw(context)
        if (floatingBall) FloatingBallManager.enable(context)
    }
    LazyColumn(
        state = listState,
        modifier = modifier.fillMaxSize().background(Paper),
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
            Modifier.fillMaxWidth().height(BottomBarHeight).padding(horizontal = 42.dp, vertical = 2.dp),
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
        Modifier.width(72.dp).clip(RoundedCornerShape(14.dp)).clickable { onSelect(tab) }.padding(vertical = 3.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        when (tab) {
            MainTab.Chat -> ChatTabIcon(active, label)
            MainTab.History -> HistoryTabIcon(active, label)
            MainTab.Settings -> SettingsTabIcon(active, label)
        }
        Spacer(Modifier.height(1.dp))
        Text(label, color = if (active) Cocoa else LightMuted, fontSize = 9.sp, lineHeight = 12.sp)
    }
}

@Composable
private fun ChatTabIcon(active: Boolean, contentDescription: String) {
    Box(
        Modifier.size(28.dp).semantics { this.contentDescription = contentDescription },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(28.dp)) {
            scale(0.70f, pivot = Offset(size.width / 2f, size.height / 2f)) {
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
        Modifier.size(28.dp).semantics { this.contentDescription = contentDescription },
    ) {
        scale(0.70f, pivot = Offset(size.width / 2f, size.height / 2f)) {
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
        Modifier.size(28.dp).semantics { this.contentDescription = contentDescription },
    ) {
        scale(0.70f, pivot = Offset(size.width / 2f, size.height / 2f)) {
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
    val listState = rememberLazyListState()
    rememberFollowLatestListState(
        state = listState,
        contentKey = Triple(job.sequence, job.processArtifacts?.length, job.thinkingText?.length),
        enabled = active,
    )
    Scaffold(containerColor = Paper) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(horizontal = 18.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(22.dp),
        ) {
            item {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    IconButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterStart)) {
                        Icon(Lucide.ArrowLeft, "返回")
                    }
                    Text("核实详情", fontSize = 18.sp, color = Ink, fontWeight = FontWeight.Bold)
                }
            }
            if (active) {
                item { LiveGeneration(job) }
            } else {
                item { StructuredReport(job) }
                job.processArtifacts?.takeIf { it.isNotBlank() }?.let {
                    item { ProcessHistory(it) }
                }
                job.thinkingText?.takeIf { it.isNotBlank() }?.let {
                    item { DisclosureSection("模型思考过程", it, initiallyExpanded = false) }
                }
            }
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
private fun LiveGeneration(job: JobEntity) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("核验记录", color = Ink, fontWeight = FontWeight.Black, fontSize = 21.sp)
        Text("公开资料返回后会立即显示，你可以边等待边查看。", color = Muted, fontSize = 12.sp)
        job.processArtifacts?.takeIf { it.isNotBlank() }?.let {
            ProcessArtifacts(it, active = true)
        }
        when {
            job.processArtifacts.isNullOrBlank() -> ActiveProcessNode(job.displayText)
            !job.thinkingText.isNullOrBlank() -> ActiveProcessNode("正在综合研判") {
                ExpandableText("查看模型思考", job.thinkingText, initiallyExpanded = false)
            }
            else -> ActiveProcessNode(job.displayText)
        }
    }
}

@Composable
private fun ActiveProcessNode(title: String, content: (@Composable () -> Unit)? = null) {
    val transition = rememberInfiniteTransition(label = "active-node")
    val nodeAlpha by transition.animateFloat(
        initialValue = .42f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(850), RepeatMode.Reverse),
        label = "active-node-alpha",
    )
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Box(Modifier.width(24.dp).padding(top = 5.dp), contentAlignment = Alignment.TopCenter) {
            Box(Modifier.size(11.dp).alpha(nodeAlpha).clip(CircleShape).background(Orange))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, color = Ink, fontWeight = FontWeight.Bold, fontSize = 15.sp)
            content?.invoke()
        }
    }
}

@Composable
private fun ProcessHistory(raw: String) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("核验过程", color = Ink, fontWeight = FontWeight.Black, fontSize = 19.sp)
            ProcessArtifacts(raw, active = false, initiallyExpanded = false)
        }
    }
}

@Composable
private fun ProcessArtifacts(
    raw: String,
    active: Boolean,
    initiallyExpanded: Boolean = true,
) {
    val artifacts = remember(raw) {
        raw.lineSequence().filter { it.isNotBlank() }.mapNotNull {
            runCatching { Gson().fromJson(it, JobEventPayloadDto::class.java) }.getOrNull()
        }.toList()
    }
    val uriHandler = LocalUriHandler.current
    artifacts.forEachIndexed { index, artifact ->
        var expanded by remember(artifact.kind, artifact.title) { mutableStateOf(initiallyExpanded) }
        var showAll by remember(artifact.kind, artifact.title) { mutableStateOf(false) }
        val hasFollowingNode = index < artifacts.lastIndex || active
        Row(
            Modifier.fillMaxWidth().drawBehind {
                if (hasFollowingNode) {
                    val x = 5.dp.toPx()
                    drawLine(
                        Divider,
                        Offset(x, 13.dp.toPx()),
                        Offset(x, size.height + 7.dp.toPx()),
                        1.dp.toPx(),
                    )
                }
            }.padding(bottom = if (hasFollowingNode) 18.dp else 0.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Box(Modifier.width(24.dp).padding(top = 5.dp), contentAlignment = Alignment.TopStart) {
                Box(Modifier.size(11.dp).clip(CircleShape).background(Ink))
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(
                    Modifier.fillMaxWidth().clickable { expanded = !expanded },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(artifact.title ?: "阶段结果", color = Ink, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        artifact.summary?.let { Text(it, color = Muted, fontSize = 11.sp, lineHeight = 17.sp) }
                    }
                    Icon(
                        if (expanded) Lucide.ChevronUp else Lucide.ChevronDown,
                        if (expanded) "收起" else "展开",
                        tint = LightMuted,
                        modifier = Modifier.size(16.dp),
                    )
                }
                AnimatedVisibility(expanded) {
                    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        val allItems = artifact.items.orEmpty()
                        val visibleItems = if (showAll) allItems else allItems.take(4)
                        visibleItems.forEach { item -> ArtifactRow(item, uriHandler) }
                        if (allItems.size > 4) {
                            Text(
                                if (showAll) "收起" else "查看全部 ${allItems.size} 项",
                                color = Cocoa,
                                fontSize = 11.sp,
                                modifier = Modifier.clickable { showAll = !showAll }.padding(vertical = 4.dp),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ArtifactRow(
    item: com.mimotrust.xiaozhen.data.remote.JobArtifactItemDto,
    uriHandler: androidx.compose.ui.platform.UriHandler,
) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).background(Color.White)
            .clickable(enabled = !item.url.isNullOrBlank()) {
                item.url?.let { runCatching { uriHandler.openUri(it) } }
            }.padding(horizontal = 11.dp, vertical = 9.dp),
        verticalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            item.label?.let { Text(it, color = Cocoa, fontSize = 10.sp, fontWeight = FontWeight.Bold) }
            item.meta?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.width(7.dp))
                Text(it, color = LightMuted, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            if (!item.url.isNullOrBlank()) {
                Spacer(Modifier.width(5.dp))
                Icon(Lucide.ExternalLink, "打开来源", tint = Muted, modifier = Modifier.size(11.dp))
            }
        }
        item.text?.let { Text(it, color = Muted, fontSize = 12.sp, lineHeight = 18.sp) }
    }
}

@Composable
private fun VerificationModeControl(selected: String, onChange: (String) -> Unit) {
    Row(Modifier.clip(RoundedCornerShape(10.dp)).background(Soft).padding(3.dp)) {
        listOf("speed" to "快速", "quality" to "高质量").forEach { (mode, label) ->
            val active = selected == mode
            Text(
                label,
                color = if (active) Ink else Muted,
                fontSize = 11.sp,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Normal,
                modifier = Modifier.clip(RoundedCornerShape(8.dp))
                    .background(if (active) Color.White else Color.Transparent)
                    .clickable { onChange(mode) }
                    .padding(horizontal = 12.dp, vertical = 7.dp),
            )
        }
    }
}

@Composable
private fun DisclosureSection(title: String, content: String, initiallyExpanded: Boolean) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(Modifier.fillMaxWidth().padding(20.dp)) {
            ExpandableText(title, content, initiallyExpanded)
        }
    }
}

@Composable
private fun ExpandableText(title: String, content: String, initiallyExpanded: Boolean) {
    var expanded by remember(title) { mutableStateOf(initiallyExpanded) }
    Row(
        Modifier.fillMaxWidth().clickable { expanded = !expanded }.padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(title, color = Ink, fontWeight = FontWeight.Bold, fontSize = 16.sp)
        Icon(
            if (expanded) Lucide.ChevronUp else Lucide.ChevronDown,
            if (expanded) "收起" else "展开",
            tint = Muted,
            modifier = Modifier.size(18.dp),
        )
    }
    AnimatedVisibility(expanded) {
        Text(
            content,
            color = Muted,
            fontSize = 13.sp,
            lineHeight = 21.sp,
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )
    }
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun StructuredReport(job: JobEntity) {
    val report = remember(job.reportJson) {
        job.reportJson?.let {
            runCatching { Gson().fromJson(it, VerificationDetailsDto::class.java) }.getOrNull()
        }
    }
    if (report == null) {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            job.claimDetails?.let { DetailSection("逐主张核验", it) }
            job.narrativeAnalysis?.let { DetailSection("叙事分析", it) }
            job.evidenceGaps?.let { DetailSection("待补证据", it) }
            job.keyEvidence?.let { DetailSection("关键依据", it) }
        }
        return
    }
    val evidenceById = report.evidenceUsed.orEmpty().associateBy { it.id }
    Column(verticalArrangement = Arrangement.spacedBy(30.dp)) {
        ReportHero(job, report)
        report.narrativeAnalysis?.let { narrative ->
            Column(verticalArrangement = Arrangement.spacedBy(15.dp)) {
                ReportSectionTitle(Lucide.MessagesSquare, "叙事分析")
                Column(
                    Modifier.fillMaxWidth().drawBehind {
                        drawLine(Color(0xFF8A6A2D), Offset(1.5.dp.toPx(), 0f), Offset(1.5.dp.toPx(), size.height), 3.dp.toPx())
                    }.padding(start = 18.dp),
                    verticalArrangement = Arrangement.spacedBy(11.dp),
                ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("判断", color = LightMuted, fontSize = 10.sp)
                            Spacer(Modifier.width(10.dp))
                            Text(narrative.verdict ?: "未单独判断", color = Ink, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        }
                        narrative.explanation?.let { Text(it, color = Muted, fontSize = 13.sp, lineHeight = 22.sp) }
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(7.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                            narrative.methods.orEmpty().take(4).forEach { method ->
                                Text(
                                    method,
                                    color = Color(0xFF765B29),
                                    fontSize = 11.sp,
                                    modifier = Modifier.border(1.dp, Color(0xFFDED3BB), RoundedCornerShape(6.dp))
                                        .background(Color(0xFFF7F2E8), RoundedCornerShape(6.dp))
                                        .padding(horizontal = 9.dp, vertical = 6.dp),
                                )
                            }
                        }
                }
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ReportSectionTitle(Lucide.ListChecks, "逐项核验")
            report.claimChecks.orEmpty().forEach { check ->
                ClaimReportCard(check, evidenceById)
            }
        }
        report.evidenceGaps?.takeIf { it.isNotEmpty() }?.let { gaps ->
            Column(verticalArrangement = Arrangement.spacedBy(13.dp)) {
                ReportSectionTitle(Lucide.FileQuestion, "待补证据")
                gaps.forEachIndexed { index, gap ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                        Text("${index + 1}", color = LightMuted, fontSize = 11.sp, modifier = Modifier.width(24.dp))
                        Text(gap, color = Muted, fontSize = 13.sp, lineHeight = 21.sp, modifier = Modifier.weight(1f))
                    }
                }
            }
        }
        report.evidenceUsed?.takeIf { it.isNotEmpty() }?.let { EvidenceSection(it) }
    }
}

@Composable
private fun ReportHero(job: JobEntity, report: VerificationDetailsDto) {
    val verdict = report.overallVerdict ?: job.verdict ?: "待核实"
    val tone = verdictToneColor(verdict)
    val visibleElapsed = rememberVisibleElapsed(job)
    val selectedCount = report.evidenceSelectedCount.takeIf { it > 0 } ?: job.evidenceCount
    val reviewedCount = report.evidenceReviewedCount.takeIf { it > 0 } ?: selectedCount
    Column(
        Modifier.fillMaxWidth().border(1.dp, Divider, RoundedCornerShape(16.dp))
            .background(Soft, RoundedCornerShape(16.dp)).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(13.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(46.dp).clip(CircleShape).background(tone.copy(alpha = .10f)), contentAlignment = Alignment.Center) {
                Icon(verdictIcon(verdict), null, tint = tone, modifier = Modifier.size(23.dp))
            }
            Spacer(Modifier.width(13.dp))
            Column(Modifier.weight(1f)) {
                Text("综合判定", color = LightMuted, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                Text(verdict, color = Ink, fontSize = 27.sp, lineHeight = 33.sp, fontWeight = FontWeight.Black)
            }
        }
        report.topic?.takeIf { it.isNotBlank() }?.let {
            Text(it, color = Ink, fontSize = 15.sp, lineHeight = 23.sp, fontWeight = FontWeight.Bold)
        }
        Text(report.conclusion ?: job.conclusion.orEmpty(), color = Muted, fontSize = 15.sp, lineHeight = 24.sp)
        report.sharingAdvice?.takeIf { it.isNotBlank() }?.let {
            Row(verticalAlignment = Alignment.Top) {
                Text("传播建议", color = Ink, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(9.dp))
                Text(it, color = Muted, fontSize = 12.sp, lineHeight = 19.sp, modifier = Modifier.weight(1f))
            }
        }
        Row(
            Modifier.fillMaxWidth().border(1.dp, Divider, RoundedCornerShape(10.dp))
                .background(Color.White, RoundedCornerShape(10.dp)),
        ) {
            ReportMetric(report.claimChecks.orEmpty().size.toString(), "项主张", Modifier.weight(1f))
            ReportMetric(reviewedCount.toString(), "条已审阅", Modifier.weight(1f), divider = true)
            ReportMetric(selectedCount.toString(), "条入选", Modifier.weight(1f), divider = true)
        }
        Text("分析用时 ${formatElapsed(visibleElapsed)}", color = LightMuted, fontSize = 10.sp)
    }
}

@Composable
private fun ReportMetric(value: String, label: String, modifier: Modifier, divider: Boolean = false) {
    Column(
        modifier.drawBehind {
            if (divider) drawLine(Divider, Offset.Zero, Offset(0f, size.height), 1.dp.toPx())
        }
            .padding(vertical = 11.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(value, color = Ink, fontSize = 16.sp, fontWeight = FontWeight.Bold)
        Text(label, color = LightMuted, fontSize = 10.sp)
    }
}

@Composable
private fun ReportSectionTitle(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = LightMuted, modifier = Modifier.size(19.dp))
        Spacer(Modifier.width(9.dp))
        Text(title, color = Ink, fontWeight = FontWeight.Black, fontSize = 21.sp)
    }
}

@Composable
private fun ClaimReportCard(check: ClaimCheckDto, evidenceById: Map<String?, EvidenceDto>) {
    val verdict = check.verdict ?: "待核实"
    Column(
        Modifier.fillMaxWidth().border(1.dp, Divider, RoundedCornerShape(16.dp))
            .background(Color.White, RoundedCornerShape(16.dp)).padding(17.dp),
        verticalArrangement = Arrangement.spacedBy(11.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(check.claimId ?: "主张", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            check.category?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.width(8.dp))
                Text(it, color = LightMuted, fontSize = 11.sp)
            }
            Spacer(Modifier.weight(1f))
            Text(
                verdict,
                color = verdictToneColor(verdict),
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.background(verdictToneColor(verdict).copy(alpha = .10f), CircleShape)
                    .padding(horizontal = 10.dp, vertical = 6.dp),
            )
        }
        check.claim?.let { Text(it, color = Ink, fontSize = 15.sp, lineHeight = 23.sp, fontWeight = FontWeight.Bold) }
        check.evidenceSufficiency?.takeIf { it.isNotBlank() }?.let {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("证据充分度", color = LightMuted, fontSize = 10.sp)
                Spacer(Modifier.width(9.dp))
                Text(it, color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }
        }
        check.basis?.let { Text(it, color = Muted, fontSize = 13.sp, lineHeight = 21.sp) }
        check.uncertainty?.takeIf { it.isNotBlank() }?.let {
            Row(Modifier.fillMaxWidth().background(Soft).padding(horizontal = 12.dp, vertical = 10.dp)) {
                Text("不确定性", color = Ink, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(9.dp))
                Text(it, color = Muted, fontSize = 11.sp, lineHeight = 18.sp, modifier = Modifier.weight(1f))
            }
        }
        val sources = check.sourceIds.orEmpty().mapNotNull { evidenceById[it] }
        if (sources.isEmpty()) {
            Text("本项没有引用具体证据", color = LightMuted, fontSize = 11.sp)
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
                sources.forEach { EvidenceLink(it, compact = true) }
            }
        }
    }
}

@Composable
private fun EvidenceSection(evidence: List<EvidenceDto>) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ReportSectionTitle(Lucide.BookOpenCheck, "关键依据")
        evidence.forEach { EvidenceLink(it, compact = false) }
    }
}

@Composable
private fun EvidenceLink(item: EvidenceDto, compact: Boolean) {
    val uriHandler = LocalUriHandler.current
    val modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(if (compact) 8.dp else 14.dp))
        .background(if (compact) Soft else Color.White)
        .then(if (compact) Modifier else Modifier.border(1.dp, Divider, RoundedCornerShape(14.dp)))
        .clickable(enabled = !item.url.isNullOrBlank()) {
            item.url?.let { runCatching { uriHandler.openUri(it) } }
        }.padding(horizontal = if (compact) 11.dp else 15.dp, vertical = if (compact) 9.dp else 14.dp)
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        val metadata = listOfNotNull(
            item.id?.takeIf { it.isNotBlank() },
            item.author?.takeIf { it.isNotBlank() },
            item.publishedDate?.takeIf { it.isNotBlank() },
        )
        if (metadata.isNotEmpty()) Text(metadata.joinToString(" · "), color = LightMuted, fontSize = 10.sp)
        Row(verticalAlignment = Alignment.Top) {
            Text(
                item.title ?: item.url.orEmpty(),
                color = if (compact) Muted else Ink,
                fontSize = if (compact) 11.sp else 14.sp,
                lineHeight = if (compact) 17.sp else 21.sp,
                fontWeight = if (compact) FontWeight.Normal else FontWeight.Bold,
                modifier = Modifier.weight(1f),
            )
            if (!item.url.isNullOrBlank()) {
                Spacer(Modifier.width(7.dp))
                Icon(Lucide.ExternalLink, "打开来源", tint = Muted, modifier = Modifier.size(14.dp))
            }
        }
        item.relation?.takeIf { it.isNotBlank() }?.let {
            Text(it, color = Cocoa, fontSize = 11.sp, lineHeight = 17.sp)
        }
        if (!compact) item.snippet?.takeIf { it.isNotBlank() }?.let {
            Text(it, color = Muted, fontSize = 12.sp, lineHeight = 19.sp, maxLines = 4, overflow = TextOverflow.Ellipsis)
        }
    }
}

private fun verdictToneColor(verdict: String): Color = when (verdict) {
    "可信", "大体可信", "属实", "大体属实" -> Color(0xFF3F6C52)
    "不实", "虚假", "误导" -> Color(0xFF99534C)
    "真假混合", "部分属实" -> Color(0xFF8A6A2D)
    else -> Color(0xFF5F6670)
}

private fun verdictIcon(verdict: String): androidx.compose.ui.graphics.vector.ImageVector = when (verdict) {
    "可信", "大体可信", "属实", "大体属实" -> Lucide.BadgeCheck
    "不实", "虚假", "误导" -> Lucide.BadgeX
    "真假混合", "部分属实" -> Lucide.CircleDotDashed
    else -> Lucide.CircleHelp
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

private data class SourcePresentation(
    val label: String,
    val detail: String,
    val isVideo: Boolean,
)

private fun sourcePresentation(value: String): SourcePresentation {
    val normalized = value.trim()
    val lower = normalized.lowercase(Locale.ROOT)
    val recognizedVideo = "douyin.com" in lower || "iesdouyin.com" in lower ||
        "bilibili.com" in lower || "b23.tv" in lower ||
        "xiaohongshu.com" in lower || "xhslink.com" in lower ||
        "kuaishou.com" in lower || "weibo.com" in lower || "weibo.cn" in lower ||
        lower.startsWith("content://") || lower.endsWith(".mp4") ||
        lower.endsWith(".mov") || lower.endsWith(".m4v")
    val platform = when {
        "douyin.com" in lower || "iesdouyin.com" in lower -> "抖音视频"
        "bilibili.com" in lower || "b23.tv" in lower -> "哔哩哔哩视频"
        "xiaohongshu.com" in lower || "xhslink.com" in lower -> "小红书视频"
        "kuaishou.com" in lower -> "快手视频"
        "weibo.com" in lower || "weibo.cn" in lower -> "微博视频"
        lower.startsWith("content://") -> "相册视频"
        lower.endsWith(".mp4") || lower.endsWith(".mov") || lower.endsWith(".m4v") -> "本地视频"
        lower.startsWith("http://") || lower.startsWith("https://") -> "网页来源"
        else -> "用户提供的核实内容"
    }
    val detail = when {
        lower.startsWith("content://") -> "已从设备相册选择"
        lower.startsWith("http://") || lower.startsWith("https://") -> runCatching {
            URI(normalized).host?.removePrefix("www.")
        }.getOrNull().takeUnless { it.isNullOrBlank() } ?: normalized
        else -> normalized.replace('\n', ' ').take(52).ifBlank { "等待读取来源信息" }
    }
    return SourcePresentation(platform, detail, recognizedVideo)
}

private val ChinaZoneId: ZoneId = ZoneId.of("Asia/Shanghai")

private fun formatCreatedAt(value: String): String = runCatching {
    Instant.parse(value).atZone(ChinaZoneId).format(DateTimeFormatter.ofPattern("MM月dd日 HH:mm"))
}.getOrDefault("最近核实")

private fun formatMessageTime(value: String, offsetMilliseconds: Long = 0): String = runCatching {
    Instant.parse(value).plusMillis(offsetMilliseconds).atZone(ChinaZoneId)
        .format(DateTimeFormatter.ofPattern("HH:mm"))
}.getOrDefault("")

private fun formatElapsed(milliseconds: Long): String {
    val seconds = milliseconds / 1000
    return if (seconds < 60) "${seconds}s" else "${seconds / 60}m ${seconds % 60}s"
}

@Composable
private fun rememberFollowLatestListState(
    state: LazyListState,
    contentKey: Any?,
    enabled: Boolean,
) {
    var followLatest by remember { mutableStateOf(true) }
    LaunchedEffect(state) {
        snapshotFlow {
            val layout = state.layoutInfo
            val last = layout.visibleItemsInfo.lastOrNull()
            val atBottom = layout.totalItemsCount == 0 || (
                last?.index == layout.totalItemsCount - 1 &&
                    last.offset + last.size <= layout.viewportEndOffset + 8
                )
            state.isScrollInProgress to atBottom
        }.collectLatest { (scrolling, atBottom) ->
            when {
                atBottom -> followLatest = true
                scrolling -> followLatest = false
            }
        }
    }
    LaunchedEffect(contentKey, enabled) {
        if (enabled && followLatest) {
            delay(40)
            val lastIndex = state.layoutInfo.totalItemsCount - 1
            if (lastIndex >= 0) state.animateScrollToItem(lastIndex, 100_000)
        }
    }
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
