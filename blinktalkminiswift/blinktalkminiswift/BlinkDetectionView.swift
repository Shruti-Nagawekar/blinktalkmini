//
//  BlinkDetectionView.swift
//  blinktalkminiswift
//
//  Created for BlinkTalk blink detection feature
//

import SwiftUI

struct BlinkDetectionView: View {
    @StateObject private var cameraManager = CameraManager()
    @State private var isSessionActive = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Camera preview
            if cameraManager.permissionGranted {
                CameraPreview(cameraManager: cameraManager)
                    .frame(maxWidth: .infinity)
                    .aspectRatio(4/3, contentMode: .fit)
                    .clipped()
                    .cornerRadius(12)
                    .padding(.horizontal)
            } else {
                // Permission denied or not granted
                VStack(spacing: 16) {
                    Image(systemName: "camera.fill")
                        .font(.system(size: 48))
                        .foregroundColor(.gray)
                    Text("Camera permission required")
                        .font(.system(size: 18, weight: .medium))
                        .foregroundColor(.secondary)
                    Text("Please enable camera access in Settings")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .aspectRatio(4/3, contentMode: .fit)
                .background(Color.gray.opacity(0.1))
                .cornerRadius(12)
                .padding(.horizontal)
            }
            
            Spacer()
            
            // Buttons
            VStack(spacing: 16) {
                Button(action: {
                    // Start Session action
                    print("BlinkDetectionView: Start Session button pressed")
                    isSessionActive = true
                    setupFrameSending()
                    print("BlinkDetectionView: Frame sending setup complete, isSessionActive: \(isSessionActive)")
                }) {
                    Text("Start Session")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.green)
                        .cornerRadius(12)
                }
                .disabled(!cameraManager.permissionGranted || isSessionActive)
                
                Button(action: {
                    // End Session action
                    isSessionActive = false
                    cameraManager.frameHandler = nil
                }) {
                    Text("End Session")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.red)
                        .cornerRadius(12)
                }
                .disabled(!cameraManager.permissionGranted || !isSessionActive)
            }
            .padding(.horizontal, 40)
            .padding(.bottom, 50)
        }
        .navigationTitle("Blink Detection")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            cameraManager.startSession()
        }
        .onDisappear {
            isSessionActive = false
            cameraManager.frameHandler = nil
            cameraManager.stopSession()
        }
    }
    
    private func setupFrameSending() {
        // Send frames every 3rd frame (about 10 fps) to avoid overwhelming server
        var localCounter = 0
        print("BlinkDetectionView: Setting up frame handler")
        cameraManager.frameHandler = { image in
            // Check if session is still active
            if !self.isSessionActive {
                return
            }
            
            localCounter += 1
            if localCounter % 3 == 0 {
                let frameId = UUID().uuidString
                print("BlinkDetectionView: Sending frame \(frameId) (counter: \(localCounter))")
                // Move network call to background queue to avoid blocking main thread
                DispatchQueue.global(qos: .utility).async {
                    NetworkManager.shared.sendFrame(image, frameId: frameId, saveFrame: false) { success, message in
                        if success {
                            print("BlinkDetectionView: Frame \(frameId) sent successfully")
                        } else {
                            print("BlinkDetectionView: Failed to send frame \(frameId): \(message)")
                        }
                    }
                }
            }
        }
        print("BlinkDetectionView: Frame handler set")
    }
}

