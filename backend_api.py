sffrom fastapi import FastAPI, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import cv2
import threading
from deepface import DeepFace

# FastAPI App
app = FastAPI()

# Database Setup
DATABASE_URL = "sqlite:///./emotions.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Emotion Model for Database
class EmotionEntry(Base):
    __tablename__ = "emotions"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    emotion_type = Column(String, index=True)  # 'facial' or 'speech'
    emotion_label = Column(String)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Data Model for API Input
class EmotionInput(BaseModel):
    emotion_type: str  # 'facial' or 'speech'
    emotion_label: str

# Endpoint to Log Emotion
@app.post("/log_emotion/")
def log_emotion(emotion: EmotionInput, db: sessionmaker = Depends(get_db)):
    new_entry = EmotionEntry(emotion_type=emotion.emotion_type, emotion_label=emotion.emotion_label)
    db.add(new_entry)
    db.commit()
    return {"message": "Emotion logged successfully", "data": emotion}

# Endpoint to Fetch Logged Emotions
@app.get("/get_emotions/")
def get_emotions(db: sessionmaker = Depends(get_db)):
    emotions = db.query(EmotionEntry).all()
    return {"emotions": emotions}

# 📌 Video Streaming Generator
def generate_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break

        try:
            emotions = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            detected_emotion = emotions[0]['dominant_emotion']

            # Draw emotion label on the frame
            cv2.putText(frame, f"Emotion: {detected_emotion}", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        except Exception as e:
            print("⚠ Error detecting emotion:", e)

        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    cap.release()

# 📌 Video Streaming Route
@app.get("/video_feed/", response_class=StreamingResponse)
async def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
