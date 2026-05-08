package com.benwabschall.movrscanner;

import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.EditText;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.Camera;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageCapture;
import androidx.camera.core.ImageCaptureException;
import androidx.camera.core.ImageProxy;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ScanActivity extends AppCompatActivity {
    private static final int MAX_IMAGE_COUNT = 24;
    private static final String TAG = "ScanActivity";

    private Button captureButton;
    private ProgressBar progressBar;
    private TextView tvSceneName, tvProgress;
    private PreviewView previewView;
    private List<File> capturedImageFiles = new ArrayList<>();
    private int imageCount = 0;
    private String sceneName;

    private ImageCapture imageCapture;
    private ExecutorService cameraExecutor;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_scan);

        // UI Elements
        previewView = findViewById(R.id.previewView);
        captureButton = findViewById(R.id.captureButton);
        progressBar = findViewById(R.id.progressBar);
        tvSceneName = findViewById(R.id.tv_scene_name);
        tvProgress = findViewById(R.id.tv_progress);

        // Back button logic
        Button btnBack = findViewById(R.id.btn_back);
        btnBack.setOnClickListener(v -> finish());

        // Capture button logic
        captureButton.setOnClickListener(v -> {
            if (imageCount < MAX_IMAGE_COUNT) {
                captureImage();
            }
            disableCapture();
        });

        // Set up initial progress bar state
        progressBar.setMax(MAX_IMAGE_COUNT);
        updateProgressBar();

        // Request scene name before capturing
        requestSceneName();

        // Initialize CameraX
        startCamera();

        cameraExecutor = Executors.newSingleThreadExecutor();
    }

    private void startCamera() {
        ListenableFuture<ProcessCameraProvider> cameraProviderFuture =
                ProcessCameraProvider.getInstance(this);

        cameraProviderFuture.addListener(() -> {
            try {
                ProcessCameraProvider cameraProvider = cameraProviderFuture.get();

                CameraSelector cameraSelector = new CameraSelector.Builder()
                        .requireLensFacing(CameraSelector.LENS_FACING_BACK)
                        .build();

                androidx.camera.core.Preview preview = new androidx.camera.core.Preview.Builder().build();
                preview.setSurfaceProvider(previewView.getSurfaceProvider());

                imageCapture = new ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                        .build();

                cameraProvider.unbindAll();
                Camera camera = cameraProvider.bindToLifecycle(
                        this, cameraSelector, preview, imageCapture
                );

            } catch (Exception e) {
                Log.e(TAG, "Failed to start camera", e);
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void captureImage() {
        if (imageCount >= MAX_IMAGE_COUNT) return;

        File photoFile = new File(getExternalFilesDir(null), "photo_" + imageCount + ".jpg");

        ImageCapture.OutputFileOptions outputOptions = new ImageCapture.OutputFileOptions.Builder(photoFile).build();

        imageCapture.takePicture(outputOptions, cameraExecutor, new ImageCapture.OnImageSavedCallback() {
            @Override
            public void onImageSaved(@NonNull ImageCapture.OutputFileResults outputFileResults) {
                Log.d(TAG, "Image saved for scan session.");
                capturedImageFiles.add(photoFile);
                runOnUiThread(() -> {
                    imageCount++;
                    updateProgressBar();
                    if (imageCount == MAX_IMAGE_COUNT) {
                        showSendImagesDialog();
                    }
                });
            }

            @Override
            public void onError(@NonNull ImageCaptureException exception) {
                Log.e(TAG, "Image capture failed", exception);
            }
        });
    }

    private void disableCapture() {
        captureButton.setEnabled(imageCount < MAX_IMAGE_COUNT);
    }

    private void updateProgressBar() {
        progressBar.setProgress(imageCount);
        tvProgress.setText(imageCount + " / " + MAX_IMAGE_COUNT);
    }

    private void requestSceneName() {
        EditText input = new EditText(this);
        input.setHint("e.g., Living Room, Office Chair, Couch");

        new AlertDialog.Builder(this)
                .setTitle("What are we scanning today?")
                .setMessage("Give your model a name before we get started.")
                .setView(input)
                .setCancelable(false)
                .setPositiveButton("OK", (dialog, which) -> handleSceneNameInput(input.getText().toString().trim()))
                .setNegativeButton("Cancel", (dialog, which) -> goToMainActivity())
                .show();
    }

    private void handleSceneNameInput(String inputName) {
        if (inputName.isEmpty()) {
            Toast.makeText(this, "Model name cannot be empty!", Toast.LENGTH_LONG).show();
            requestSceneName();
        } else {
            sceneName = inputName.trim();
            tvSceneName.setText("Scanning: " + sceneName);
        }
    }

    private void showSendImagesDialog() {
        new AlertDialog.Builder(this)
                .setTitle("Send Images")
                .setMessage("You have captured " + MAX_IMAGE_COUNT + " images. Would you like to send them?")
                .setPositiveButton("Yes", (dialog, which) -> showUploadDialog())
                .setNegativeButton("No", (dialog, which) -> goToMainActivity())
                .setCancelable(false)
                .show();
    }

    private void showUploadDialog() {
        AlertDialog uploadingDialog = new AlertDialog.Builder(this)
                .setTitle("Uploading...")
                .setMessage("Please wait while your images are being uploaded.")
                .setCancelable(false)
                .show();

        new android.os.Handler().postDelayed(() -> sendImagesToProxy(uploadingDialog), 100);
    }

    private void sendImagesToProxy(AlertDialog uploadingDialog) {
        if (sceneName == null || sceneName.isEmpty()) {
            Log.e(TAG, "Scene name is null or empty!");
            runOnUiThread(() -> Toast.makeText(this, "Scene name is required!", Toast.LENGTH_LONG).show());
            uploadingDialog.dismiss();
            return;
        }
        if (capturedImageFiles.isEmpty()) {
            Log.e(TAG, "No images to upload!");
            runOnUiThread(() -> Toast.makeText(this, "No images captured!", Toast.LENGTH_LONG).show());
            uploadingDialog.dismiss();
            return;
        }

        Log.d(TAG, "Uploading images to configured API endpoint...");
        PhotoUploader.uploadPhotos(sceneName, capturedImageFiles, new PhotoUploader.UploadCallback() {
            @Override
            public void onSuccess(String response) {
                Log.d(TAG, "Upload successful.");
                runOnUiThread(() -> {
                    Toast.makeText(ScanActivity.this, "Upload successful!", Toast.LENGTH_LONG).show();
                    uploadingDialog.dismiss();
                    resetScanActivity();
                });
            }

            @Override
            public void onFailure(String error) {
                Log.e(TAG, "Upload failed: " + error);
                runOnUiThread(() -> {
                    Toast.makeText(ScanActivity.this, "Upload failed: " + error, Toast.LENGTH_LONG).show();
                    uploadingDialog.dismiss();
                    resetScanActivity();
                });
            }
        });
    }

    private void resetScanActivity() {
        capturedImageFiles.clear();
        imageCount = 0;
        progressBar.setProgress(0);
        tvProgress.setText("0 / " + MAX_IMAGE_COUNT);
        tvSceneName.setText("Scanning: ");
        captureButton.setEnabled(true);
        startCamera();
    }

    private void goToMainActivity() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
        finish();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (!cameraExecutor.isShutdown()) {
            cameraExecutor.shutdownNow();
        }
    }
}
