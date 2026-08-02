package com.mimotrust.xiaozhen.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.mimotrust.xiaozhen.data.JobRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.UUID

class MainViewModel(private val repository: JobRepository) : ViewModel() {
    val jobs: StateFlow<List<com.mimotrust.xiaozhen.data.local.JobEntity>> = repository.observeJobs()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init { viewModelScope.launch { repository.reconnectActiveJobs() } }

    fun verify(text: String, verificationMode: String) {
        if (text.isBlank()) return
        viewModelScope.launch {
            repository.createSharedJob(
                text.trim(),
                UUID.randomUUID().toString(),
                verificationMode,
            )
        }
    }
}

class MainViewModelFactory(private val repository: JobRepository) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = MainViewModel(repository) as T
}

