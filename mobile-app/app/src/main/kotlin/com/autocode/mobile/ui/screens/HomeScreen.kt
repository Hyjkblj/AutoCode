package com.autocode.mobile.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.autocode.mobile.AppViewModel
import com.autocode.mobile.displayLabel

@Composable
internal fun HomeTab(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val project = state.dynamicProjects.find { it.id == state.selectedProjectId }
    val mode =
        if (state.baseUrl.isBlank()) {
            "离线模拟（未配置控制面地址）"
        } else {
            "已配置控制面：${state.baseUrl}"
        }
    Column(Modifier.padding(20.dp)) {
        Text("首页", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        Text("已登录：${state.session?.displayName ?: "—"}")
        Spacer(Modifier.height(8.dp))
        Text("当前项目：${project?.name ?: state.selectedProjectId ?: "未选择"}")
        Spacer(Modifier.height(8.dp))
        Text("生成目标：${state.generationTarget.displayLabel()}")
        Spacer(Modifier.height(8.dp))
        Text("代理身份：${state.agentProfile.displayLabel()}")
        Spacer(Modifier.height(8.dp))
        Text(mode, style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(20.dp))
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text(
                    "支持：登录鉴权、项目选择与生成配置。\n" +
                        "支持：自然语言任务创建、状态同步与审批提醒。\n" +
                        "支持：产物查看、在线预览、访问链接与发布历史。",
                )
            }
        }
    }
}
