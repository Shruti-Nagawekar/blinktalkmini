//
//  CameraManager.swift
//  blinktalkminiswift
//
//  Created for BlinkTalk camera capture
//

import AVFoundation
import UIKit
import Combine

class CameraManager: NSObject, ObservableObject {
    @Published var permissionGranted = false
    @Published var isSessionRunning = false
    
    private let captureSession = AVCaptureSession()
    private let videoOutput = AVCaptureVideoDataOutput()
    private let sessionQueue = DispatchQueue(label: "camera.session.queue")
    lazy var previewLayer: AVCaptureVideoPreviewLayer = {
        let layer = AVCaptureVideoPreviewLayer(session: captureSession)
        layer.videoGravity = .resizeAspectFill
        return layer
    }()
    
    var frameHandler: ((UIImage) -> Void)?
    
    override init() {
        super.init()
        checkPermission()
    }
    
    func checkPermission() {
        let status = AVCaptureDevice.authorizationStatus(for: .video)
        print("CameraManager: Permission status: \(status.rawValue)")
        switch status {
        case .authorized:
            permissionGranted = true
            print("CameraManager: Permission granted, setting up session")
            setupSession()
        case .notDetermined:
            print("CameraManager: Permission not determined, requesting")
            requestPermission()
        default:
            permissionGranted = false
            print("CameraManager: Permission denied")
        }
    }
    
    private func requestPermission() {
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            DispatchQueue.main.async {
                print("CameraManager: Permission request result: \(granted)")
                self?.permissionGranted = granted
                if granted {
                    self?.setupSession()
                }
            }
        }
    }
    
    private func setupSession() {
        print("CameraManager: Starting session setup")
        sessionQueue.async { [weak self] in
            guard let self = self else { return }
            
            self.captureSession.beginConfiguration()
            self.captureSession.sessionPreset = .medium
            
            // Setup front camera input
            guard let videoDevice = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) else {
                print("CameraManager: Failed to get front camera device")
                self.captureSession.commitConfiguration()
                return
            }
            
            guard let videoDeviceInput = try? AVCaptureDeviceInput(device: videoDevice) else {
                print("CameraManager: Failed to create device input")
                self.captureSession.commitConfiguration()
                return
            }
            
            guard self.captureSession.canAddInput(videoDeviceInput) else {
                print("CameraManager: Cannot add device input to session")
                self.captureSession.commitConfiguration()
                return
            }
            
            self.captureSession.addInput(videoDeviceInput)
            print("CameraManager: Camera input added")
            
            // Setup video output
            if self.captureSession.canAddOutput(self.videoOutput) {
                self.captureSession.addOutput(self.videoOutput)
                self.videoOutput.setSampleBufferDelegate(self, queue: DispatchQueue(label: "camera.output.queue"))
                self.videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA)]
                print("CameraManager: Video output added")
            } else {
                print("CameraManager: Cannot add video output to session")
            }
            
            self.captureSession.commitConfiguration()
            print("CameraManager: Session configuration committed")
        }
    }
    
    func startSession() {
        print("CameraManager: startSession called, permissionGranted: \(permissionGranted)")
        guard permissionGranted else {
            print("CameraManager: Cannot start session - permission not granted")
            return
        }
        sessionQueue.async { [weak self] in
            guard let self = self else { return }
            if !self.captureSession.isRunning {
                print("CameraManager: Starting capture session")
                self.captureSession.startRunning()
                DispatchQueue.main.async {
                    self.isSessionRunning = true
                    print("CameraManager: Session running: \(self.captureSession.isRunning)")
                }
            } else {
                print("CameraManager: Session already running")
            }
        }
    }
    
    func stopSession() {
        print("CameraManager: stopSession called")
        sessionQueue.async { [weak self] in
            guard let self = self else { return }
            if self.captureSession.isRunning {
                print("CameraManager: Stopping capture session")
                self.captureSession.stopRunning()
                DispatchQueue.main.async {
                    self.isSessionRunning = false
                }
            }
        }
    }
    
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate
extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let imageBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        
        let ciImage = CIImage(cvImageBuffer: imageBuffer)
        let context = CIContext()
        
        guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else { return }
        let uiImage = UIImage(cgImage: cgImage)
        
        // Call frame handler if set (on background queue to avoid blocking)
        if let handler = self.frameHandler {
            DispatchQueue.global(qos: .userInitiated).async {
                handler(uiImage)
            }
        } else {
            // Log occasionally if handler is not set (every 100 frames to avoid spam)
            if Int.random(in: 0..<100) == 0 {
                print("CameraManager: Frame handler not set, frames not being processed")
            }
        }
    }
}

