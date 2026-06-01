package com.autocode.mobile.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.autocode.mobile.AppViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ProjectsTab(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val shouldUseMockFallback = state.baseUrl.isBlank() || state.session == null
    val projects =
        if (state.dynamicProjects.isEmpty() && shouldUseMockFallback) {
            vm.mockProjects
        } else {
            state.dynamicProjects
        }
    PullToRefreshBox(
        isRefreshing = state.isRefreshingProjects,
        onRefresh = { vm.refreshProjects() },
        modifier = Modifier.fillMaxSize(),
    ) {
        Column(Modifier.padding(20.dp).verticalScroll(rememberScrollState())) {
            Text("选择项目", style = MaterialTheme.typography.headlineSmall)
            Spacer(Modifier.height(8.dp))
            Text(
                "项目编号需与控制面保持一致（默认 proj-1 与后端测试数据对齐）。",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(16.dp))
            if (projects.isEmpty()) {
                Text(
                    "暂无可用项目，下拉可从控制面刷新。",
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(10.dp))
            }
            projects.forEach { p ->
                val active = p.id == state.selectedProjectId
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
                        .clickable { vm.selectProject(p.id) },
                ) {
                    RowWithProject(name = p.name, active = active)
                }
            }
        }
    }
}

@Composable
private fun RowWithProject(name: String, active: Boolean) {
    Column(Modifier.padding(16.dp)) {
        Text(name, style = MaterialTheme.typography.titleMedium)
        if (active) {
            Spacer(Modifier.height(4.dp))
            Text("当前", color = MaterialTheme.colorScheme.primary)
        }
    }
}
