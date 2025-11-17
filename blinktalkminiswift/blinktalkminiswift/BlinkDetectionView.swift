//
//  BlinkDetectionView.swift
//  blinktalkminiswift
//
//  Created for BlinkTalk blink detection feature
//

import SwiftUI

struct BlinkDetectionView: View {
    var body: some View {
        VStack {
            Text("Blink Detection")
                .font(.system(size: 32, weight: .bold, design: .rounded))
                .padding()
            
            Spacer()
            
            // Placeholder for camera preview
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.gray.opacity(0.3))
                .frame(maxWidth: .infinity)
                .aspectRatio(4/3, contentMode: .fit)
                .padding(.horizontal)
            
            Spacer()
            
            // Placeholder for buttons
            VStack(spacing: 16) {
                Button(action: {
                    // Start Session action
                }) {
                    Text("Start Session")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.green)
                        .cornerRadius(12)
                }
                
                Button(action: {
                    // End Session action
                }) {
                    Text("End Session")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.red)
                        .cornerRadius(12)
                }
            }
            .padding(.horizontal, 40)
            .padding(.bottom, 50)
        }
        .navigationTitle("Blink Detection")
        .navigationBarTitleDisplayMode(.inline)
    }
}

