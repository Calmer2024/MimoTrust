package com.mimotrust.xiaozhen.ui

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
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
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mimotrust.xiaozhen.R
import com.mimotrust.xiaozhen.data.local.JobEntity
import com.mimotrust.xiaozhen.overlay.FloatingBallManager
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.max

private enum class MainTab { Chat, History, Settings }

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
            containerColor = Color.White,
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
    val context = LocalContext.current
    val speechLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { input = it }
        }
    }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()) { bitmap ->
        photo = bitmap
    }
    val send = {
        if (input.isNotBlank()) {
            onVerify(input.trim(), verificationMode)
            input = ""
            photo = null
        }
    }

    Box(modifier.fillMaxSize().background(Color.White)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 22.dp, top = 18.dp, end = 22.dp, bottom = 134.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item { BrandHeader() }
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
                items(jobs.take(3), key = { it.jobId }) { JobCard(it, onOpen) }
            }
        }

        ChatComposer(
            value = input,
            onValueChange = { input = it },
            photo = photo,
            onClearPhoto = { photo = null },
            onCamera = { cameraLauncher.launch(null) },
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
private fun BrandHeader() {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Image(
            painter = painterResource(R.drawable.xiaozhen_logo),
            contentDescription = "小真",
            modifier = Modifier.size(54.dp).clip(RoundedCornerShape(18.dp)),
            contentScale = ContentScale.Crop,
        )
        Spacer(Modifier.width(12.dp))
        Column {
            Text("小真", fontSize = 20.sp, fontWeight = FontWeight.Black, color = Ink)
            Text("让事实更清楚", fontSize = 13.sp, color = Muted)
        }
        Spacer(Modifier.weight(1f))
        Box(Modifier.clip(CircleShape).background(OrangeSoft).padding(horizontal = 12.dp, vertical = 7.dp)) {
            Text("AI 核验助手", color = Orange, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun StartPrompt(onPick: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(11.dp)) {
        Text("你可以这样问", color = Muted, fontSize = 13.sp)
        listOf(
            "这个视频里说的是真的吗？",
            "帮我核实这条新闻的来源",
            "这段网传消息可信吗？",
        ).forEach { prompt ->
            Row(
                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(SurfaceSoft)
                    .clickable { onPick(prompt) }.padding(17.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Default.Link, null, tint = Ink, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(12.dp))
                Text(prompt, color = Ink, fontWeight = FontWeight.Medium)
                Spacer(Modifier.weight(1f))
                Icon(Icons.Default.ChevronRight, null, tint = LightMuted, modifier = Modifier.size(20.dp))
            }
        }
    }
}

@Composable
private fun ChatComposer(
    value: String,
    onValueChange: (String) -> Unit,
    photo: Bitmap?,
    onClearPhoto: () -> Unit,
    onCamera: () -> Unit,
    onVoice: () -> Unit,
    onSend: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth().imePadding().background(Color.White)
            .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp),
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
        Row(
            modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(30.dp)).background(SurfaceSoft).padding(5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onCamera) { Icon(Icons.Default.CameraAlt, "拍照", tint = Ink) }
            TextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("粘贴链接或输入核实内容…", color = LightMuted, fontSize = 14.sp) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { onSend() }),
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Color.Transparent,
                    unfocusedContainerColor = Color.Transparent,
                    disabledContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                ),
            )
            IconButton(onClick = onVoice) { Icon(Icons.Default.Mic, "语音输入", tint = Ink) }
            IconButton(onClick = onSend, enabled = value.isNotBlank()) {
                Box(
                    Modifier.size(40.dp).clip(CircleShape).background(if (value.isNotBlank()) Ink else Divider),
                    contentAlignment = Alignment.Center,
                ) { Icon(Icons.AutoMirrored.Filled.Send, "发送", tint = Color.White, modifier = Modifier.size(19.dp)) }
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
        colors = CardDefaults.cardColors(containerColor = if (active) Ink else SurfaceSoft),
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
                        failed -> Icon(Icons.Default.ErrorOutline, null, tint = Orange, modifier = Modifier.size(20.dp))
                        else -> Icon(Icons.Default.CheckCircle, null, tint = Ink, modifier = Modifier.size(20.dp))
                    }
                }
                Spacer(Modifier.width(11.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        when { active -> "小真正在核实"; failed -> "核实未完成"; else -> job.verdict ?: "核实完成" },
                        color = if (active) Color.White else Ink,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        if (active) job.displayText else formatCreatedAt(job.createdAt),
                        color = if (active) Color.White.copy(alpha = .58f) else Muted,
                        fontSize = 12.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(formatElapsed(visibleElapsed), color = if (active) Color.White.copy(alpha = .58f) else Muted, fontSize = 11.sp)
            }
            Text(
                job.headline ?: job.sourceText,
                color = if (active) Color.White else Ink,
                fontWeight = FontWeight.Bold,
                fontSize = 17.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (active) {
                LinearProgressIndicator(
                    progress = { job.progress.coerceIn(0, 100) / 100f },
                    modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
                    color = Orange,
                    trackColor = Color.White.copy(alpha = .16f),
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(processLabel(job.progress), color = Color.White.copy(alpha = .72f), fontSize = 12.sp)
                    Text("${job.progress}%", color = Color.White.copy(alpha = .72f), fontSize = 12.sp)
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
        modifier.fillMaxSize().background(Color.White),
        contentPadding = PaddingValues(22.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Column(Modifier.padding(bottom = 10.dp)) {
                Text("核实历史", fontSize = 29.sp, fontWeight = FontWeight.Black, color = Ink)
                Spacer(Modifier.height(5.dp))
                Text("你发给小真的内容都在这里", color = Muted, fontSize = 14.sp)
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
            Icon(Icons.Default.History, null, tint = LightMuted, modifier = Modifier.size(28.dp))
        }
        Spacer(Modifier.height(15.dp))
        Text("还没有核实记录", fontWeight = FontWeight.Bold, color = Ink)
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
        modifier.fillMaxSize().background(Color.White),
        contentPadding = PaddingValues(22.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Column(Modifier.padding(bottom = 8.dp)) {
                Text("设置", fontSize = 29.sp, fontWeight = FontWeight.Black, color = Ink)
                Text("管理小真的使用偏好", color = Muted, fontSize = 14.sp)
            }
        }
        item {
            SettingsGroup {
                SettingsToggle(Icons.Default.ChatBubble, "悬浮核验球", "刷视频时常驻，点击即可发起核验", floatingBall) { enabled ->
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
                SettingsToggle(Icons.Default.Notifications, "核实完成提醒", "结果生成后及时通知", notifications) { notifications = it }
                HorizontalDivider(color = Divider, modifier = Modifier.padding(start = 54.dp))
                SettingsToggle(Icons.Default.DarkMode, "深色模式", "即将支持", darkMode, enabled = false) { darkMode = it }
            }
        }
        item {
            SettingsGroup {
                SettingsLink(Icons.Default.Security, "隐私与数据", "核实记录仅保存在你的设备")
                HorizontalDivider(color = Divider, modifier = Modifier.padding(start = 54.dp))
                SettingsLink(Icons.Default.Info, "关于小真", "版本 0.1.0")
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
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(SurfaceSoft).padding(horizontal = 16.dp)) { content() }
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
    Row(Modifier.fillMaxWidth().padding(vertical = 15.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = if (enabled) Ink else LightMuted, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = if (enabled) Ink else LightMuted, fontWeight = FontWeight.Medium)
            Text(subtitle, color = LightMuted, fontSize = 11.sp)
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange, enabled = enabled)
    }
}

@Composable
private fun SettingsLink(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, subtitle: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 17.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Ink, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = Ink, fontWeight = FontWeight.Medium)
            Text(subtitle, color = LightMuted, fontSize = 11.sp)
        }
        Icon(Icons.Default.ChevronRight, null, tint = LightMuted, modifier = Modifier.size(20.dp))
    }
}

@Composable
private fun BottomNavigation(selected: MainTab, onSelect: (MainTab) -> Unit) {
    Row(
        Modifier.fillMaxWidth().height(78.dp).background(Color.White).padding(horizontal = 42.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        NavigationItem(MainTab.Chat, selected, "对话", Icons.Default.ChatBubble, onSelect)
        NavigationItem(MainTab.History, selected, "历史", Icons.Default.History, onSelect)
        NavigationItem(MainTab.Settings, selected, "设置", Icons.Default.Settings, onSelect)
    }
}

@Composable
private fun NavigationItem(
    tab: MainTab,
    selected: MainTab,
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    onSelect: (MainTab) -> Unit,
) {
    val active = tab == selected
    Column(
        Modifier.width(72.dp).clip(RoundedCornerShape(16.dp)).clickable { onSelect(tab) }.padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(icon, label, tint = if (active) Ink else LightMuted, modifier = Modifier.size(23.dp))
        Spacer(Modifier.height(3.dp))
        Text(label, color = if (active) Ink else LightMuted, fontSize = 11.sp, fontWeight = if (active) FontWeight.Bold else FontWeight.Normal)
    }
}

@Composable
private fun JobDetail(job: JobEntity, onBack: () -> Unit) {
    val active = job.status == "queued" || job.status == "running"
    val visibleElapsed = rememberVisibleElapsed(job)
    Scaffold(containerColor = Color.White) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(22.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
                    Text("核实详情", fontSize = 22.sp, fontWeight = FontWeight.Black, color = Ink)
                }
            }
            item {
                Card(shape = RoundedCornerShape(28.dp), colors = CardDefaults.cardColors(containerColor = Ink)) {
                    Column(Modifier.padding(23.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(job.verdict ?: if (active) "核实进行中" else "核实未完成", color = Orange, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                        Text(job.headline ?: job.sourceText, color = Color.White, fontSize = 25.sp, lineHeight = 32.sp, fontWeight = FontWeight.Black)
                        Text(job.conclusion ?: job.displayText, color = Color.White.copy(alpha = .72f), lineHeight = 21.sp)
                        HorizontalDivider(color = Color.White.copy(alpha = .14f))
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Metric("公开证据", "${job.evidenceCount} 条")
                            Metric("分析用时", formatElapsed(visibleElapsed))
                            Metric("流程进度", "${job.progress}%")
                        }
                    }
                }
            }
            job.claimDetails?.let { item { DetailSection("逐主张核验", it) } }
            job.narrativeAnalysis?.let { item { DetailSection("叙事分析", it) } }
            job.evidenceGaps?.let { item { DetailSection("待补证据", it) } }
            job.keyEvidence?.let { item { DetailSection("关键依据", it) } }
            item { Timeline(job) }
            item { Text("AI 辅助核验，仅供信息参考。请结合原始来源与完整语境判断。", color = Muted, fontSize = 12.sp, lineHeight = 18.sp) }
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
    Card(shape = RoundedCornerShape(26.dp), colors = CardDefaults.cardColors(containerColor = SurfaceSoft)) {
        Column(Modifier.padding(22.dp)) {
            Text("核实过程", fontWeight = FontWeight.Black, fontSize = 19.sp, color = Ink)
            Spacer(Modifier.height(18.dp))
            stages.forEachIndexed { index, (label, threshold) ->
                Row(verticalAlignment = Alignment.Top) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(18.dp).clip(CircleShape).background(if (job.progress >= threshold) Orange else Divider))
                        if (index < stages.lastIndex) Box(Modifier.width(2.dp).height(34.dp).background(if (job.progress >= stages[index + 1].second) Orange else Divider))
                    }
                    Spacer(Modifier.width(14.dp))
                    Column {
                        Text(label, fontWeight = if (job.progress >= threshold) FontWeight.Bold else FontWeight.Normal, color = if (job.progress >= threshold) Ink else Muted)
                        if (job.progress in threshold until (stages.getOrNull(index + 1)?.second ?: 101)) Text("正在处理…", color = Orange, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun Metric(label: String, value: String) {
    Column { Text(value, color = Color.White, fontWeight = FontWeight.Bold); Text(label, color = Color.White.copy(alpha = .52f), fontSize = 11.sp) }
}

private fun processLabel(progress: Int): String = when (progress) {
    in 0..12 -> "正在读取链接"
    in 13..35 -> "正在理解内容"
    in 36..58 -> "正在拆解主张"
    in 59..82 -> "正在检索与比对来源"
    else -> "正在整理核实结论"
}

private fun formatCreatedAt(value: String): String = runCatching {
    Instant.parse(value).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("MM月dd日 HH:mm"))
}.getOrDefault("最近核实")

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
