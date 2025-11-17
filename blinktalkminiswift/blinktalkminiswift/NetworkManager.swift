//
//  NetworkManager.swift
//  blinktalkminiswift
//
//  Created for BlinkTalk frame communication
//

import Foundation
import UIKit

class NetworkManager {
    static let shared = NetworkManager()
    
    // Server configuration
    private let serverIP = "100.70.127.109"
    private let serverPort = 8080
    private var baseURL: String {
        "http://\(serverIP):\(serverPort)"
    }
    
    private init() {}
    
    /// Send a frame (UIImage) to the server from camera stream
    /// - Parameters:
    ///   - image: The UIImage to send
    ///   - frameId: Optional identifier for the frame
    ///   - saveFrame: Whether to save this frame to disk on server (default: false for streaming)
    ///   - completion: Optional callback with success status and message (nil for fire-and-forget streaming)
    func sendFrame(_ image: UIImage, frameId: String? = nil, saveFrame: Bool = false, completion: ((Bool, String) -> Void)? = nil) {
        guard let imageData = image.jpegData(compressionQuality: 0.7) else {
            completion?(false, "Failed to convert image to JPEG")
            return
        }
        
        // Convert image to base64
        let base64String = imageData.base64EncodedString()
        
        // Create frame ID if not provided
        let id = frameId ?? UUID().uuidString
        
        // Prepare JSON payload
        let payload: [String: Any] = [
            "frame": base64String,
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "frame_id": id,
            "save_frame": saveFrame
        ]
        
        guard let jsonData = try? JSONSerialization.data(withJSONObject: payload) else {
            completion?(false, "Failed to create JSON payload")
            return
        }
        
        // Create request
        guard let url = URL(string: "\(baseURL)/") else {
            completion?(false, "Invalid server URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData
        request.timeoutInterval = 5.0  // Shorter timeout for streaming
        
        // Send request (fire-and-forget for streaming, or with completion)
        print("NetworkManager: Sending POST request to \(url.absoluteString)")
        URLSession.shared.dataTask(with: request) { data, response, error in
            guard let completion = completion else {
                // Fire-and-forget - log if there's an error
                if let error = error {
                    print("NetworkManager: Fire-and-forget request failed: \(error.localizedDescription)")
                }
                return
            }
            
            DispatchQueue.main.async {
                if let error = error {
                    print("NetworkManager: Request error: \(error.localizedDescription)")
                    completion(false, "Network error: \(error.localizedDescription)")
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    print("NetworkManager: Invalid response type")
                    completion(false, "Invalid response")
                    return
                }
                
                print("NetworkManager: Response status code: \(httpResponse.statusCode)")
                guard httpResponse.statusCode == 200 else {
                    print("NetworkManager: Server returned error: HTTP \(httpResponse.statusCode)")
                    completion(false, "Server error: HTTP \(httpResponse.statusCode)")
                    return
                }
                
                if let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let status = json["status"] as? String {
                    if status == "success" {
                        let message = json["message"] as? String ?? "Frame sent successfully"
                        completion(true, message)
                    } else {
                        let message = json["message"] as? String ?? "Unknown error"
                        completion(false, message)
                    }
                } else {
                    completion(false, "Failed to parse server response")
                }
            }
        }.resume()
    }
    
    /// Check if server is reachable
    /// - Parameter completion: Callback with connection status
    func checkServerConnection(completion: @escaping (Bool, String) -> Void) {
        guard let url = URL(string: "\(baseURL)/health") else {
            completion(false, "Invalid server URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 5.0
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    completion(false, "Connection failed: \(error.localizedDescription)")
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else {
                    completion(false, "Server not responding")
                    return
                }
                
                completion(true, "Server is reachable")
            }
        }.resume()
    }
}

