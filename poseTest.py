import cv2
import mediapipe as mp
import pyrealsense2 as rs
import numpy as np
from math import atan2
import time
import logging
import sys
import requests

lower_limit_armpit = 50
upper_limit_armpit = 130
lower_limit_elbow = 100
upper_limit_elbow = 180

hand_1_open = False
hand_2_open = False

# Function to calculate angles between joints
def angle(p_1, p_2, p_3):
    a = atan2(p_3[1] - p_2[1], p_3[0] - p_2[0]) - atan2(p_1[1] - p_2[1], p_1[0] - p_2[0])
    a = np.rad2deg(a)
    a = abs(a)
    if a > 180:
        a = 360 - a
    return a

# Function to determine pointing direction from angles, only pointing if one arm is extended (not both)
def get_gesture(laa, raa, lea, rea, x_vals, open_hand):
        pointing_left = (lower_limit_armpit < laa < upper_limit_armpit and lower_limit_elbow < lea < upper_limit_elbow) and not (lower_limit_armpit < raa < upper_limit_armpit) and (x_vals[2] > x_vals[0] + 0.2)
        pointing_right = (lower_limit_armpit < raa < upper_limit_armpit and lower_limit_elbow < rea < upper_limit_elbow) and not (lower_limit_armpit < laa < upper_limit_armpit) and (x_vals[1] > x_vals[3] + 0.2)

        if pointing_left:
            return "left"
        elif pointing_right:
            return "right"
        elif open_hand is not None:
            if open_hand and not (pointing_left or pointing_right):
                return "openhand"
            elif not open_hand and not (pointing_left or pointing_right):
                return "closedhand"
        else:
            return None
        
# Function to check if hand is open or not
def is_open(handLandmarks):
        
        #IDs for finger tips
        tips = [
            mp_hands.HandLandmark.THUMB_TIP,
            mp_hands.HandLandmark.INDEX_FINGER_TIP,
            mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
            mp_hands.HandLandmark.RING_FINGER_TIP,
            mp_hands.HandLandmark.PINKY_TIP
        ]
        
        #IDs for mcps
        mcp = [
            mp_hands.HandLandmark.THUMB_MCP,
            mp_hands.HandLandmark.INDEX_FINGER_MCP,
            mp_hands.HandLandmark.MIDDLE_FINGER_MCP,
            mp_hands.HandLandmark.RING_FINGER_MCP,
            mp_hands.HandLandmark.PINKY_MCP
        ]
        
        #Wrist ID
        wristID = mp_hands.HandLandmark.WRIST

        #Wrist position
        wrist = np.array([
            handLandmarks.landmark[wristID].x,
            handLandmarks.landmark[wristID].y,
            handLandmarks.landmark[wristID].z
        ])

        extendedFingers = 0

        #Loop through all tips and mcp
        for tip, mcp in zip(tips, mcp):
            tipPos = np.array([
                handLandmarks.landmark[tip].x,
                handLandmarks.landmark[tip].y,
                handLandmarks.landmark[tip].z
            ])
            
            mcpPos = np.array([
                handLandmarks.landmark[mcp].x,
                handLandmarks.landmark[mcp].y,
                handLandmarks.landmark[mcp].z
            ])
            
            #Get the vector from tips to wrist and from mcps to wrist
            wristToTip = tipPos - wrist
            wristToMcp = mcpPos - wrist
            
            #If the distance from wrist to tip is greater the finger is extended
            if np.linalg.norm(wristToTip) > np.linalg.norm(wristToMcp) + 0.05:
                extendedFingers += 1

        return extendedFingers >= 4 #Hand is open if 4 or more fingers are extended
    

# Set up Mediapipe
mp_pose = mp.solutions.pose
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


# Set up pipeline for Intel RealSense camera
pipe = rs.pipeline()
cfg = rs.config()
cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
pipe.start()

# Video Stream
with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5, static_image_mode=False) as pose, mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
    while True: 
        
        # Get frames from the camera
        frames = pipe.wait_for_frames()
        cFrame = frames.get_color_frame()
        cImage = np.asanyarray(cFrame.get_data())

        hand_open = None
        
        image = cv2.cvtColor(cImage, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        
        # Get mediapipe results
        mp_res = pose.process(image)
        hand_res = hands.process(image)

        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        try:
            landmarks = mp_res.pose_landmarks.landmark
        except:
            continue

        mp_drawing.draw_landmarks(image, mp_res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        left_shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, 
                                  landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y,
                                  landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].z])
        right_shoulder = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, 
                                   landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y,
                                   landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].z])
        left_elbow = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                               landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y,
                               landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].z])
        right_elbow = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x,
                                landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y,
                                landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].z])
        left_wrist = np.array([landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                               landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y,
                               landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].z])
        right_wrist = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x,
                                landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y,
                                landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].z])
        left_hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x,
                             landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y,
                             landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].z])
        right_hip = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x,
                              landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y,
                              landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].z])

        left_armpit_angle = angle(left_hip, left_shoulder, left_elbow)
        right_armpit_angle = angle(right_hip, right_shoulder, right_elbow)
        left_elbow_angle = angle(left_shoulder, left_elbow, left_wrist)
        right_elbow_angle = angle(right_shoulder, right_elbow, right_wrist)

        if hand_res.multi_hand_landmarks:
            right_hand = None
            for i, handLandmarks in enumerate(hand_res.multi_hand_landmarks):
                handedness = hand_res.multi_handedness[i].classification[0].label
                if handedness == "Right":
                    right_hand = handLandmarks
                    break           
            if right_hand:
                mp_drawing.draw_landmarks(image, right_hand, mp_hands.HAND_CONNECTIONS)
                hand_open = is_open(right_hand)

        gesture = get_gesture(left_armpit_angle, right_armpit_angle, left_elbow_angle, right_elbow_angle, 
                                   [left_shoulder[0], right_shoulder[0], left_wrist[0], right_wrist[0], left_elbow[0], right_elbow[0], left_hip[0], right_hip[0]],
                                     hand_open)
        server_url = 'http://192.168.0.2:5000/command'
        if gesture:
            if gesture == "left":
                print("Pointing left")
                requests.post(server_url, json={'command': gesture})
            elif gesture == "right":
                print("Pointing right")
                requests.post(server_url, json={'command': gesture})
            elif gesture == "openhand":
                print("Open hand")
                requests.post(server_url, json={'command': gesture})
            elif gesture == "closedhand":
                print("Closed hand")
                requests.post(server_url, json={'command': gesture})
        else:
            print("No gesture detected")

        cv2.imshow('Mediapipe Feed', image)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        

pipe.stop()
cv2.destroyAllWindows()

'''
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

cap = cv2.VideoCapture(0)

with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
    while cap.isOpened():
        ret, frame = cap.read()

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        
        results = pose.process(image)
        
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Extract landmarks
        try: 
            landmarks = results.pose_landmarks.landmark # you can print this out and it will show you the coordinates of each landmark
            # e.g. nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
        except:
            pass

        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        cv2.imshow('Mediapipe Feed', image)

        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows'''
