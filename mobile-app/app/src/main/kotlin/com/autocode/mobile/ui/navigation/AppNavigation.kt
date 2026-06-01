package com.autocode.mobile.ui.navigation

import android.app.Application
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.Monitoring
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.autocode.mobile.AppViewModel
import com.autocode.mobile.AppViewModelFactory
import com.autocode.mobile.ui.screens.SettingsScreen
import com.autocode.mobile.ui.screens.ArtifactDetailScreen
import com.autocode.mobile.ui.screens.ArtifactsForTaskScreen
import com.autocode.mobile.ui.screens.ArtifactsHubTab
import com.autocode.mobile.ui.screens.LoginScreen
import com.autocode.mobile.ui.screens.PublishHistoryScreen
import com.autocode.mobile.ui.screens.StatusScreen
import com.autocode.mobile.ui.screens.TaskDetailTab
import com.autocode.mobile.ui.screens.TaskListTab

private sealed class Tab(
    val route: String,
    val label: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
) {
    data object Chat : Tab("chat", "对话", Icons.Filled.ChatBubble)
    data object Assets : Tab("assets", "资产", Icons.Filled.Inventory2)
    data object Status : Tab("status", "状态", Icons.Filled.Monitoring)
    data object Settings : Tab("settings", "设置", Icons.Filled.Settings)
}

@Composable
fun AutoCodeApp() {
    val app = LocalContext.current.applicationContext as Application
    val vm: AppViewModel = viewModel(factory = AppViewModelFactory.create(app))
    val state by vm.uiState.collectAsStateWithLifecycle()
    val nav = rememberNavController()

    if (state.isLoading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        return
    }

    val start = if (state.session != null) "shell" else "login"

    NavHost(navController = nav, startDestination = start) {
        composable("login") {
            LoginScreen(vm = vm)
        }
        composable("shell") {
            MainShell(vm = vm)
        }
    }

    LaunchedEffect(state.session, state.isLoading) {
        if (state.isLoading) return@LaunchedEffect
        val dest = nav.currentBackStackEntry?.destination?.route
        if (state.session != null && dest == "login") {
            nav.navigate("shell") {
                popUpTo(nav.graph.findStartDestination().id) { inclusive = true }
            }
        }
        if (state.session == null && dest == "shell") {
            nav.navigate("login") {
                popUpTo(nav.graph.findStartDestination().id) { inclusive = true }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainShell(vm: AppViewModel) {
    val innerNav = rememberNavController()
    val navBackStackEntry by innerNav.currentBackStackEntryAsState()
    val current = navBackStackEntry?.destination?.route.orEmpty()
    val showBar =
        current in
            listOf(
                Tab.Chat.route,
                Tab.Assets.route,
                Tab.Status.route,
                Tab.Settings.route,
            )

    Scaffold(
        bottomBar = {
            if (showBar) {
                NavigationBar {
                    val tabs = listOf(Tab.Chat, Tab.Assets, Tab.Status, Tab.Settings)
                    tabs.forEach { tab ->
                        val selected = current == tab.route
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                innerNav.navigate(tab.route) {
                                    popUpTo(innerNav.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = innerNav,
            startDestination = Tab.Chat.route,
            modifier = Modifier.padding(padding),
        ) {
            composable(Tab.Chat.route) {
                TaskListTab(vm, innerNav)
            }
            composable(
                route = "task/{id}",
                arguments = listOf(navArgument("id") { type = NavType.StringType }),
            ) { entry ->
                val id = entry.arguments?.getString("id").orEmpty()
                TaskDetailTab(
                    vm,
                    taskId = id,
                    onBack = { innerNav.popBackStack() },
                    innerNav = innerNav,
                )
            }
            composable(Tab.Assets.route) {
                ArtifactsHubTab(vm, innerNav)
            }
            composable(
                route = "artifacts/history",
            ) {
                PublishHistoryScreen(vm, onBack = { innerNav.popBackStack() })
            }
            composable(
                route = "artifacts/task/{taskId}",
                arguments = listOf(navArgument("taskId") { type = NavType.StringType }),
            ) { entry ->
                val tid = entry.arguments?.getString("taskId").orEmpty()
                ArtifactsForTaskScreen(
                    vm,
                    taskId = tid,
                    onBack = { innerNav.popBackStack() },
                    innerNav = innerNav,
                )
            }
            composable(
                route = "artifacts/item/{taskId}/{artifactId}",
                arguments =
                    listOf(
                        navArgument("taskId") { type = NavType.StringType },
                        navArgument("artifactId") { type = NavType.StringType },
                    ),
            ) { entry ->
                val tid = entry.arguments?.getString("taskId").orEmpty()
                val aid = entry.arguments?.getString("artifactId").orEmpty()
                ArtifactDetailScreen(
                    vm,
                    taskId = tid,
                    artifactId = aid,
                    onBack = { innerNav.popBackStack() },
                )
            }
            composable(Tab.Status.route) {
                StatusScreen(vm)
            }
            composable(Tab.Settings.route) {
                SettingsScreen(vm)
            }
        }
    }
}
