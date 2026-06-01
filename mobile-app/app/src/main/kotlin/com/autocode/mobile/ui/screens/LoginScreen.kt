package com.autocode.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.autocode.mobile.AppViewModel

@Composable
internal fun LoginRoute(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var user by rememberSaveable { mutableStateOf("") }
    var pass by rememberSaveable { mutableStateOf("") }
    var baseUrlDraft by rememberSaveable { mutableStateOf(state.baseUrl) }

    LaunchedEffect(state.baseUrl) {
        baseUrlDraft = state.baseUrl
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text = "AutoCode")
        Spacer(Modifier.height(8.dp))
        Text(
            text = "在「我的」填写控制面地址后，将使用账号登录并创建任务；" +
                "留空则离线模拟。",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = baseUrlDraft,
            onValueChange = { baseUrlDraft = it },
            label = { Text("控制面地址") },
            placeholder = { Text("例如：http://10.92.85.245:8058") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = user,
            onValueChange = { user = it },
            label = { Text("用户名") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = pass,
            onValueChange = { pass = it },
            label = { Text("密码") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        state.errorMessage?.let { msg ->
            Spacer(Modifier.height(8.dp))
            Text(text = msg, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = {
                vm.consumeError()
                vm.login(user, pass, baseUrlDraft)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("登录")
        }
    }
}
