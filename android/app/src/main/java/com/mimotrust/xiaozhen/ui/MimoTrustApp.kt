package com.mimotrust.xiaozhen.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mimotrust.xiaozhen.data.local.JobEntity

@Composable
fun MimoTrustApp(viewModel: MainViewModel, initialJobId: String?) {
    MimoTheme {
        val jobs by viewModel.jobs.collectAsStateWithLifecycle()
        var selectedId by remember { mutableStateOf(initialJobId) }
        val selected = jobs.firstOrNull { it.jobId == selectedId }
        if (selected != null) {
            JobDetail(selected) { selectedId = null }
        } else {
            Home(jobs = jobs, onVerify = viewModel::verify, onOpen = { selectedId = it.jobId })
        }
    }
}

@Composable
private fun Home(jobs: List<JobEntity>, onVerify: (String) -> Unit, onOpen: (JobEntity) -> Unit) {
    var input by remember { mutableStateOf("") }
    Scaffold(
        containerColor = Paper,
        bottomBar = { BottomBar() },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item { Header() }
            item { HeroCard() }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("发起核验", fontSize = 21.sp, fontWeight = FontWeight.Bold)
                    OutlinedTextField(
                        value = input,
                        onValueChange = { input = it },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(20.dp),
                        placeholder = { Text("粘贴视频链接或平台分享文案") },
                        minLines = 2,
                    )
                    Button(
                        onClick = { onVerify(input); input = "" },
                        enabled = input.isNotBlank(),
                        modifier = Modifier.fillMaxWidth().height(54.dp),
                        shape = RoundedCornerShape(18.dp),
                    ) {
                        Icon(Icons.Default.Security, null)
                        Spacer(Modifier.width(8.dp))
                        Text("交给小真核验", fontWeight = FontWeight.Bold)
                    }
                }
            }
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("核验任务", fontSize = 21.sp, fontWeight = FontWeight.Bold)
                    Text("${jobs.size} 项", color = Muted)
                }
            }
            if (jobs.isEmpty()) item { EmptyJobsCard() }
            items(jobs, key = { it.jobId }) { JobCard(it, onOpen) }
        }
    }
}

@Composable
private fun Header() {
    Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
        Column {
            Text("MIMO TRUST", color = Muted, fontSize = 12.sp, letterSpacing = 2.sp)
            Text("你好，我是小真", fontSize = 28.sp, fontWeight = FontWeight.Black)
        }
        Box(Modifier.size(48.dp).clip(CircleShape).background(Ink), contentAlignment = Alignment.Center) {
            Text("真", color = Color.White, fontWeight = FontWeight.Black, fontSize = 20.sp)
        }
    }
}

@Composable
private fun HeroCard() {
    Card(
        modifier = Modifier.fillMaxWidth().height(196.dp),
        shape = RoundedCornerShape(32.dp),
        colors = CardDefaults.cardColors(containerColor = Ink),
    ) {
        Box(Modifier.fillMaxSize()) {
            Canvas(Modifier.fillMaxSize()) {
                repeat(8) { index ->
                    val path = Path().apply {
                        moveTo(0f, size.height * (0.42f + index * 0.045f))
                        cubicTo(size.width * .25f, size.height * (.1f + index * .05f), size.width * .55f, size.height * (.88f - index * .025f), size.width, size.height * (.35f + index * .03f))
                    }
                    drawPath(path, Color.White.copy(alpha = .06f), style = androidx.compose.ui.graphics.drawscope.Stroke(1f))
                }
            }
            Column(Modifier.padding(24.dp).align(Alignment.TopStart)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Mic, null, tint = Color.White, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("后台语音助手", color = Color.White.copy(alpha = .72f), fontSize = 13.sp)
                }
                Spacer(Modifier.height(18.dp))
                Text("继续刷视频，\n真假交给我。", color = Color.White, fontWeight = FontWeight.Black, fontSize = 29.sp, lineHeight = 34.sp)
                Spacer(Modifier.height(14.dp))
                Text("从分享面板选择“小真核验”即可", color = Color.White.copy(alpha = .72f), fontSize = 13.sp)
            }
            Box(Modifier.padding(22.dp).size(48.dp).clip(CircleShape).background(Color.White).align(Alignment.BottomEnd), contentAlignment = Alignment.Center) {
                Icon(Icons.Default.Share, null, tint = Ink)
            }
        }
    }
}

@Composable
private fun JobCard(job: JobEntity, onOpen: (JobEntity) -> Unit) {
    val active = job.status == "queued" || job.status == "running"
    Card(
        modifier = Modifier.fillMaxWidth().clickable { onOpen(job) },
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = if (active) Ink else Color.White),
    ) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
                Box(Modifier.size(40.dp).clip(CircleShape).background(if (active) Color.White else Soft), contentAlignment = Alignment.Center) {
                    if (active) CircularProgressIndicator(Modifier.size(19.dp), color = Ink, strokeWidth = 2.dp)
                    else Icon(Icons.Default.CheckCircle, null, tint = Ink, modifier = Modifier.size(20.dp))
                }
                Text(formatElapsed(job.elapsedMs), color = if (active) Color.White.copy(alpha = .65f) else Muted, fontSize = 12.sp)
            }
            Text(job.headline ?: job.displayText, color = if (active) Color.White else Ink, fontWeight = FontWeight.Bold, fontSize = 18.sp)
            Text(job.sourceText, color = if (active) Color.White.copy(alpha = .62f) else Muted, maxLines = 2, overflow = TextOverflow.Ellipsis, fontSize = 13.sp)
            if (active) LinearProgressIndicator(progress = { job.progress / 100f }, modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape), color = Color.White, trackColor = Color.White.copy(alpha = .18f))
            else Row(verticalAlignment = Alignment.CenterVertically) {
                Text(job.verdict ?: "查看结果", fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                Icon(Icons.AutoMirrored.Filled.OpenInNew, null, modifier = Modifier.size(18.dp))
            }
        }
    }
}

@Composable
private fun EmptyJobsCard() {
    Card(shape = RoundedCornerShape(26.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Default.Share, null, tint = Muted)
            Spacer(Modifier.height(10.dp))
            Text("还没有核验任务", fontWeight = FontWeight.Bold)
            Text("在短视频分享面板中选择“小真核验”", color = Muted, fontSize = 13.sp)
        }
    }
}

@Composable
private fun JobDetail(job: JobEntity, onBack: () -> Unit) {
    Scaffold(containerColor = Paper) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = androidx.compose.foundation.layout.PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
                    Text("核验详情", fontSize = 22.sp, fontWeight = FontWeight.Black)
                }
            }
            item {
                Card(shape = RoundedCornerShape(30.dp), colors = CardDefaults.cardColors(containerColor = Ink)) {
                    Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(job.verdict ?: if (job.status == "failed") "未完成" else "核验进行中", color = Color.White.copy(alpha = .65f), fontSize = 13.sp)
                        Text(job.headline ?: job.displayText, color = Color.White, fontSize = 27.sp, fontWeight = FontWeight.Black)
                        Text(job.conclusion ?: "小真正在后台逐步核对内容与公开来源。", color = Color.White.copy(alpha = .75f), lineHeight = 21.sp)
                        HorizontalDivider(color = Color.White.copy(alpha = .15f))
                        Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween) {
                            Metric("公开证据", "${job.evidenceCount} 条")
                            Metric("分析用时", formatElapsed(job.elapsedMs))
                            Metric("流程进度", "${job.progress}%")
                        }
                    }
                }
            }
            item { Timeline(job) }
            item {
                Text("AI 辅助核验，仅供信息参考。请结合原始来源与完整语境判断。", color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
            }
        }
    }
}

@Composable
private fun Timeline(job: JobEntity) {
    val stages = listOf(
        "读取视频内容" to 8,
        "理解字幕与画面" to 22,
        "识别原子主张" to 42,
        "检索公开来源" to 66,
        "筛选直接证据" to 79,
        "生成核验结论" to 100,
    )
    Card(shape = RoundedCornerShape(28.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.padding(22.dp)) {
            Text("分析过程", fontWeight = FontWeight.Black, fontSize = 20.sp)
            Spacer(Modifier.height(18.dp))
            stages.forEachIndexed { index, (label, threshold) ->
                Row(verticalAlignment = Alignment.Top) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(18.dp).clip(CircleShape).background(if (job.progress >= threshold) Ink else Soft))
                        if (index < stages.lastIndex) Box(Modifier.width(2.dp).height(34.dp).background(if (job.progress >= stages[index + 1].second) Ink else Soft))
                    }
                    Spacer(Modifier.width(14.dp))
                    Text(label, fontWeight = if (job.progress >= threshold) FontWeight.Bold else FontWeight.Normal, color = if (job.progress >= threshold) Ink else Muted)
                }
            }
        }
    }
}

@Composable
private fun Metric(label: String, value: String) {
    Column { Text(value, color = Color.White, fontWeight = FontWeight.Bold); Text(label, color = Color.White.copy(alpha = .55f), fontSize = 11.sp) }
}

@Composable
private fun BottomBar() {
    Row(Modifier.fillMaxWidth().height(76.dp).background(Color.White).padding(horizontal = 34.dp), Arrangement.SpaceBetween, Alignment.CenterVertically) {
        Icon(Icons.Default.Home, "首页", tint = Ink)
        Icon(Icons.Default.History, "历史", tint = Color(0xFFB8B8B3))
        Box(Modifier.size(52.dp).clip(CircleShape).background(Ink), contentAlignment = Alignment.Center) { Icon(Icons.Default.Add, "新建", tint = Color.White) }
        Icon(Icons.Default.Security, "证据", tint = Color(0xFFB8B8B3))
    }
}

private fun formatElapsed(milliseconds: Long): String {
    val seconds = milliseconds / 1000
    return if (seconds < 60) "${seconds}s" else "${seconds / 60}m ${seconds % 60}s"
}
