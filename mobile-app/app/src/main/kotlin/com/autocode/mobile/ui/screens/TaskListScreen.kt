package com.autocode.mobile.ui.screens

import android.Manifest
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import com.autocode.mobile.AppViewModel
import com.autocode.mobile.ui.components.MobileUiTestTags
import com.autocode.mobile.ui.components.taskSourceLabel
import com.autocode.mobile.ui.components.taskStatusLabel
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.PermissionStatus
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class, ExperimentalPermissionsApi::class)
@Composable
internal fun TaskListTab(vm: AppViewModel, nav: NavHostController) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var prompt by rememberSaveable { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val audioPermissionState = rememberPermissionState(Manifest.permission.RECORD_AUDIO)
    var askedAudioPermission by rememberSaveable { mutableStateOf(false) }
    var voiceHint by rememberSaveable { mutableStateOf<String?>(null) }
    val list = vm.tasksForCurrentProject()
    val project = state.dynamicProjects.find { it.id == state.selectedProjectId }
    val permissionRationale =
        (audioPermissionState.status as? PermissionStatus.Denied)?.shouldShowRationale == true
    val voiceInputLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val text =
                result.data
                    ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    ?.firstOrNull()
                    ?.trim()
                    .orEmpty()
            if (text.isNotEmpty()) {
                prompt = if (prompt.isBlank()) text else "$prompt\n$text"
                voiceHint = null
            }
        }

    LaunchedEffect(state.selectedProjectId, state.baseUrl, state.session?.accessToken) {
        vm.refreshTasks()
    }

    fun startVoiceInput() {
        val intent = buildSpeechRecognizerIntent()
        if (intent.resolveActivity(context.packageManager) == null) {
            voiceHint = "当前设备不支持语音识别"
            return
        }
        runCatching { voiceInputLauncher.launch(intent) }
            .onFailure { voiceHint = "语音识别启动失败，请稍后重试" }
    }

    if (state.selectedProjectId == null) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("请先在「项目」页选择项目。")
        }
        return
    }

    Column(Modifier.padding(16.dp)) {
        TopAppBar(
            title = { Text("任务") },
            actions = {
                IconButton(
                    onClick = { vm.refreshTasks() },
                    enabled = !state.isRefreshingTasks,
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = "刷新任务")
                }
            },
        )
        if (state.isRefreshingTasks) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
        }
        Text(
            "当前项目：${project?.name ?: state.selectedProjectId}",
            modifier = Modifier.padding(bottom = 12.dp),
        )
        Row(verticalAlignment = Alignment.Top) {
            OutlinedTextField(
                value = prompt,
                onValueChange = { prompt = it },
                label = { Text("自然语言描述") },
                modifier = Modifier
                    .weight(1f)
                    .height(140.dp),
                minLines = 4,
            )
            Spacer(Modifier.width(8.dp))
            VoiceInputButton(
                permissionGranted = audioPermissionState.status.isGranted,
                onStartVoiceInput = { startVoiceInput() },
                onRequestPermission = {
                    askedAudioPermission = true
                    audioPermissionState.launchPermissionRequest()
                },
            )
        }
        if (askedAudioPermission && !audioPermissionState.status.isGranted) {
            val tip =
                if (permissionRationale) {
                    "请允许麦克风权限后再使用语音输入"
                } else {
                    "未授予麦克风权限，语音输入不可用"
                }
            Text(
                tip,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        voiceHint?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        state.errorMessage?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                vm.consumeError()
                scope.launch {
                    val id = vm.createTaskAsync(prompt)
                    if (id != null) {
                        prompt = ""
                        nav.navigate("task/$id")
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("发起任务")
        }
        Spacer(Modifier.height(16.dp))
        Text("任务列表", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(list, key = { it.id }) { t ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { nav.navigate("task/${t.id}") },
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text(t.prompt, maxLines = 2)
                        Spacer(Modifier.height(6.dp))
                        Text("${taskSourceLabel(t.source)} · ${taskStatusLabel(t.status)} · ${t.progress}%")
                    }
                }
            }
        }
    }
}

@Composable
internal fun VoiceInputButton(
    permissionGranted: Boolean,
    onStartVoiceInput: () -> Unit,
    onRequestPermission: () -> Unit,
) {
    IconButton(
        onClick = {
            if (permissionGranted) onStartVoiceInput() else onRequestPermission()
        },
        modifier =
            Modifier
                .padding(top = 4.dp)
                .testTag(MobileUiTestTags.VOICE_INPUT_BUTTON),
    ) {
        Icon(Icons.Filled.Mic, contentDescription = "语音输入")
    }
}

private fun buildSpeechRecognizerIntent(): Intent =
    Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        putExtra(RecognizerIntent.EXTRA_PROMPT, "请说出你的任务描述")
    }
