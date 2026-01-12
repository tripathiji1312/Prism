import cv2
import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

left_eye_indices = [33, 133, 160, 159, 158, 153, 144, 145]
right_eye_indices = [362, 263, 387, 386, 385, 384, 373, 374]

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam")

while True:
    success, frame = cap.read()
    if not success:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            h, w, _ = frame.shape

            def draw_roi(indices, color):
                xs = [int(face_landmarks.landmark[i].x * w) for i in indices]
                ys = [int(face_landmarks.landmark[i].y * h) for i in indices]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)
                if x_max > x_min and y_max > y_min:
                    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)

            draw_roi(left_eye_indices, (0, 255, 0))
            draw_roi(right_eye_indices, (255, 0, 0))
            fx = int(face_landmarks.landmark[10].x * w)
            fy = int(face_landmarks.landmark[10].y * h)
            box_w, box_h = 100, 80  
            x_min, x_max = fx - box_w//2, fx + box_w//2
            y_min, y_max = fy - box_h//2, fy + box_h//2
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2)

    cv2.imshow("Face Mesh + ROIs", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()

