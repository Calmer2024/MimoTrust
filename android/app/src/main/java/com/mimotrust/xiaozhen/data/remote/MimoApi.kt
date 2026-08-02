package com.mimotrust.xiaozhen.data.remote

import com.mimotrust.xiaozhen.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.Part
import retrofit2.http.POST
import retrofit2.http.Path

interface MimoApi {
    @POST("v1/jobs")
    suspend fun createJob(
        @Header("X-Device-Id") deviceId: String,
        @Body request: CreateJobRequestDto,
    ): CreateJobResponseDto

    @Multipart
    @POST("v1/jobs/upload")
    suspend fun createUploadJob(
        @Header("X-Device-Id") deviceId: String,
        @Part("title") title: RequestBody,
        @Part("text") text: RequestBody,
        @Part("mode") mode: RequestBody,
        @Part("verification_mode") verificationMode: RequestBody,
        @Part("client_request_id") clientRequestId: RequestBody,
        @Part files: List<MultipartBody.Part>,
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

