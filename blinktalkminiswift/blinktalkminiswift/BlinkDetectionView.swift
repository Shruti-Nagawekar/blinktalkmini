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
    @State private var finalBlinkCount: Int? = nil
    @State private var sessionDuration: Double? = nil
    @State private var showResults = false
    
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
            
            // Results display or buttons
            if showResults {
                // Show results after session ends
                VStack(spacing: 20) {
                    Text("Session Complete")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.primary)
                    
                    if let blinkCount = finalBlinkCount {
                        VStack(spacing: 8) {
                            Text("Total Blinks")
                                .font(.system(size: 16, weight: .medium))
                                .foregroundColor(.secondary)
                            Text("\(blinkCount)")
                                .font(.system(size: 48, weight: .bold))
                                .foregroundColor(.primary)
                        }
                    }
                    
                    if let duration = sessionDuration {
                        Text("Duration: \(String(format: "%.1f", duration))s")
                            .font(.system(size: 14))
                            .foregroundColor(.secondary)
                    }
                    
                    Button(action: {
                        // Reset for new session
                        showResults = false
                        finalBlinkCount = nil
                        sessionDuration = nil
                    }) {
                        Text("Start New Session")
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.green)
                            .cornerRadius(12)
                    }
                }
                .padding(.horizontal, 40)
                .padding(.bottom, 50)
            } else {
                // Buttons
                VStack(spacing: 16) {
                    Button(action: {
                        // Start Session action
                        print("BlinkDetectionView: Start Session button pressed")
                        NetworkManager.shared.startSession { success, message in
                            if success {
                                print("BlinkDetectionView: Session started on server")
                                isSessionActive = true
                                setupFrameSending()
                                print("BlinkDetectionView: Frame sending setup complete, isSessionActive: \(isSessionActive)")
                            } else {
                                print("BlinkDetectionView: Failed to start session: \(message)")
                            }
                        }
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
                        print("BlinkDetectionView: End Session button pressed")
                        isSessionActive = false
                        cameraManager.frameHandler = nil
                        
                        NetworkManager.shared.endSession { success, blinkCount, duration in
                            if success {
                                print("BlinkDetectionView: Session ended. Blinks: \(blinkCount ?? 0)")
                                finalBlinkCount = blinkCount
                                sessionDuration = duration
                                showResults = true
                            } else {
                                print("BlinkDetectionView: Failed to end session")
                            }
                        }
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

