package com.autocode.mobile

import androidx.compose.runtime.Composable

// This file previously contained all UI code (~2540 lines).
// It has been split into modular files under ui/:
//   - ui/navigation/AppNavigation.kt  (Tab, AutoCodeApp, MainShell)
//   - ui/screens/LoginScreen.kt       (LoginRoute)
//   - ui/screens/HomeScreen.kt        (HomeTab)
//   - ui/screens/TaskListScreen.kt    (TaskListTab, VoiceInputButton)
//   - ui/screens/TaskDetailScreen.kt  (TaskDetailTab, ApprovalBottomSheet, FixLoopTimelineCard)
//   - ui/screens/AssetsScreen.kt      (ArtifactsHubTab, ArtifactsForTaskScreen, ArtifactDetailScreen, PublishHistoryScreen, DeployStatusCard, ArtifactPreviewCard)
//   - ui/screens/ProjectsScreen.kt    (ProjectsTab)
//   - ui/screens/SettingsScreen.kt    (AccountTab, RowOfTargetChips, RowOfAgentProfileChips)
//   - ui/components/AgentEventItem.kt (AgentEventItem, event helpers, payload helpers)
//   - ui/components/DiffHelpers.kt    (asDiffMarkdown, localizeDiffMetaLine, mojibake fix)
//   - ui/components/UiHelpers.kt      (MobileUiTestTags, label/status formatters)

// Re-export so MainActivity.kt (same package) continues to compile without changes.
@Composable
fun AutoCodeApp() = com.autocode.mobile.ui.navigation.AutoCodeApp()
