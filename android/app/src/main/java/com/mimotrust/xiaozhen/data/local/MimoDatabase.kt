package com.mimotrust.xiaozhen.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [JobEntity::class], version = 1, exportSchema = false)
abstract class MimoDatabase : RoomDatabase() {
    abstract fun jobs(): JobDao
}
