package com.mimotrust.xiaozhen

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import com.mimotrust.xiaozhen.ui.MimoTrustApp
import com.mimotrust.xiaozhen.ui.MainViewModel
import com.mimotrust.xiaozhen.ui.MainViewModelFactory
import com.mimotrust.xiaozhen.overlay.FloatingBallManager

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels {
        MainViewModelFactory((application as MimoTrustApplication).repository)
    }
    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        FloatingBallManager.restore(this)
        setContent { MimoTrustApp(viewModel, intent.getStringExtra("job_id")) }
    }
}
