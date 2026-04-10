package com.autocode.mobile

import android.Manifest
import android.os.Bundle
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import com.autocode.mobile.ui.theme.AutoCodeMobileTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestPostNotificationPermissionIfNeeded()
        enableEdgeToEdge()
        setContent {
            AutoCodeMobileTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    AutoCodeApp()
                }
            }
        }
    }

    private fun requestPostNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted =
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        if (granted) return
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_POST_NOTIFICATIONS)
    }

    private companion object {
        private const val REQUEST_POST_NOTIFICATIONS = 1001
    }
}
