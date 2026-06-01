package com.autocode.mobile.ui.navigation

import android.app.Application
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
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
import com.autocode.mobile.ui.screens.AccountTab
import com.autocode.mobile.ui.screens.ArtifactDetailScreen
import com.autocode.mobile.ui.screens.ArtifactsForTaskScreen
import com.autocode.mobile.ui.screens.ArtifactsHubTab
import com.autocode.mobile.ui.screens.HomeTab
import com.autocode.mobile.ui.screens.LoginRoute
import com.autocode.mobile.ui.screens.ProjectsTab
import com.autocode.mobile.ui.screens.PublishHistoryScreen
import com.autocode.mobile.ui.screens.TaskDetailTab
import com.autocode.mobile.ui.screens.TaskListTab

private sealed class Tab(
    val route: String,
    val label: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
) {
    data object Home : Tab("home", "首页", Icons.Filled.Home)
    data object Tasks : Tab("tasks", "任务", Icons.AutoMirrored.Filled.List)
    data object Projects : Tab("projects", "项目", Icons.Filled.Folder)
    data object Account : Tab("account", "我的", Icons.Filled.Person)
    data object Artifacts : Tab("artifacts", "产物", Icons.Filled.AttachFile)
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
            LoginRoute(vm = vm)
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
                Tab.Home.route,
                Tab.Tasks.route,
                Tab.Projects.route,
                Tab.Account.route,
                Tab.Artifacts.route,
            )

    Scaffold(
        bottomBar = {
            if (showBar) {
                NavigationBar {
                    val tabs = listOf(Tab.Home, Tab.Tasks, Tab.Artifacts, Tab.Projects, Tab.Account)
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
            startDestination = Tab.Home.route,
            modifier = Modifier.padding(padding),
        ) {
            composable(Tab.Home.route) {
                HomeTab(vm)
            }
            composable(Tab.Tasks.route) {
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
            composable(Tab.Artifacts.route) {
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
            composable(Tab.Projects.route) {
                ProjectsTab(vm)
            }
            composable(Tab.Account.route) {
                AccountTab(vm)
            }
        }
    }
}
