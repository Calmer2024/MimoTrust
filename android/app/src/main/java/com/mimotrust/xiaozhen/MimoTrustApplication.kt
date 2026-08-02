package com.mimotrust.xiaozhen

import android.app.Application
import androidx.room.Room
import com.mimotrust.xiaozhen.data.JobRepository
import com.mimotrust.xiaozhen.data.local.MimoDatabase
import com.mimotrust.xiaozhen.data.remote.MimoApiFactory
import com.mimotrust.xiaozhen.notification.VerificationNotifier

class MimoTrustApplication : Application() {
    lateinit var repository: JobRepository
        private set

    override fun onCreate() {
        super.onCreate()
        val database = Room.databaseBuilder(this, MimoDatabase::class.java, "mimo-trust.db")
            .addMigrations(MimoDatabase.MIGRATION_1_2, MimoDatabase.MIGRATION_2_3)
            .build()
        val notifier = VerificationNotifier(this)
        notifier.createChannel()
        repository = JobRepository(
            api = MimoApiFactory.create(),
            okHttpClient = MimoApiFactory.httpClient,
            dao = database.jobs(),
            notifier = notifier,
            deviceId = DeviceIdentity.get(this),
        )
    }
}

