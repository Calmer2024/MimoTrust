package com.mimotrust.xiaozhen.data.remote

import com.mimotrust.xiaozhen.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

interface MimoApi {
    @POST("v1/jobs")
    suspend fun createJob(
        @Header("X-Device-Id") deviceId: String,
        @Body request: CreateJobRequestDto,
    ): CreateJobResponseDto

    @GET("v1/jobs/{jobId}/result")
    suspend fun result(@Path("jobId") jobId: String): JobResultDto
}

object MimoApiFactory {
    val httpClient: OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
        .build()

    fun create(): MimoApi = Retrofit.Builder()
        .baseUrl(BuildConfig.MIMO_API_BASE_URL)
        .client(httpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(MimoApi::class.java)
}

