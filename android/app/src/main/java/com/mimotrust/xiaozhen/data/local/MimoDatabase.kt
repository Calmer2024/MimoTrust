package com.mimotrust.xiaozhen.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(entities = [JobEntity::class], version = 2, exportSchema = false)
abstract class MimoDatabase : RoomDatabase() {
    abstract fun jobs(): JobDao

    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN claimDetails TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN narrativeAnalysis TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN evidenceGaps TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN keyEvidence TEXT")
            }
        }
    }
}
