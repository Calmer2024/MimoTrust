package com.mimotrust.xiaozhen.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(entities = [JobEntity::class], version = 7, exportSchema = false)
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

        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN sharingAdvice TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN uncertaintyNote TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN reportUrl TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN aiDisclaimer TEXT")
            }
        }

        val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN extractedMetadata TEXT")
            }
        }

        val MIGRATION_4_5 = object : Migration(4, 5) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN thinkingText TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN reportDraft TEXT")
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN reportJson TEXT")
            }
        }

        val MIGRATION_5_6 = object : Migration(5, 6) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN processArtifacts TEXT")
            }
        }

        val MIGRATION_6_7 = object : Migration(6, 7) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE verification_jobs ADD COLUMN attachmentsJson TEXT")
            }
        }
    }
}
