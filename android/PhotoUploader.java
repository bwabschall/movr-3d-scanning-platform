package com.benwabschall.movrscanner;

import okhttp3.*;
import android.util.Log;
import java.io.File;
import java.io.IOException;
import java.util.List;

public class PhotoUploader {

    private static final String PROXY_URL = BuildConfig.API_BASE_URL + "/upload";
    private static final OkHttpClient client = new OkHttpClient();
    private static final String TAG = "PhotoUploader";

    public interface UploadCallback {
        void onSuccess(String response);
        void onFailure(String error);
    }

    public static void uploadPhotos(String sceneName, List<File> imageFiles, UploadCallback callback) {
        Log.d(TAG, "Uploading scan images for scene: " + sceneName);

        try {
            MultipartBody.Builder multipartBuilder = new MultipartBody.Builder().setType(MultipartBody.FORM);
            multipartBuilder.addFormDataPart("sceneName", sceneName);

            for (File imageFile : imageFiles) {
                multipartBuilder.addFormDataPart(
                        "image", imageFile.getName(),
                        RequestBody.create(imageFile, MediaType.parse("image/jpeg"))
                );
            }

            RequestBody requestBody = multipartBuilder.build();

            Request request = new Request.Builder()
                    .url(PROXY_URL)
                    .post(requestBody)
                    .build();

            client.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                    Log.e(TAG, "Upload failed: " + e.getMessage(), e);
                    callback.onFailure("Upload failed: " + e.getMessage());
                }

                @Override
                public void onResponse(Call call, Response response) throws IOException {
                    if (response.isSuccessful() && response.body() != null) {
                        String responseBody = response.body().string();
                        Log.d(TAG, "Upload successful.");
                        callback.onSuccess(responseBody);
                    } else {
                        Log.e(TAG, "Upload failed with status code: " + response.code());
                        callback.onFailure("Upload failed with status: " + response.code());
                    }
                }
            });

        } catch (Exception e) {
            Log.e(TAG, "Failed to build request: " + e.getMessage(), e);
            callback.onFailure("Failed to build request: " + e.getMessage());
        }
    }
}
