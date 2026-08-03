package com.mimotrust.xiaozhen.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface JobDao {
    @Query("SELECT * FROM verification_jobs ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<JobEntity>>

    @Query("SELECT * FROM verification_jobs WHERE jobId = :jobId")
    fun observe(jobId: String): Flow<JobEntity?>

    @Query("SELECT * FROM verification_jobs WHERE jobId = :jobId")
    suspend fun get(jobId: String): JobEntity?

    @Query("SELECT * FROM verification_jobs WHERE status IN ('queued', 'running')")
    suspend fun active(): List<JobEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(job: JobEntity)
}

