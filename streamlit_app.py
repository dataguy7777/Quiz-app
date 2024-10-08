# quiz_app.py

import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------
# Configuration and Setup
# ---------------------------

# Load environment variables from .env file
load_dotenv()

# Configure Logging
logging.basicConfig(
    filename='quiz_app.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

logger = logging.getLogger(__name__)

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'quiz_app')
DB_USER = os.getenv('DB_USER', 'quiz_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'your_secure_password')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define Base for declarative models
Base = declarative_base()

# ---------------------------
# Database Models
# ---------------------------

class Question(Base):
    """
    Represents a quiz question in the database.

    Attributes:
        id (int): Primary key.
        question_text (str): The text of the question.
        option_a (str): Text for option A.
        option_b (str): Text for option B.
        option_c (str): Text for option C.
        option_d (str): Text for option D.
        correct_option (str): The correct option ('A', 'B', 'C', 'D').
        explanation (str): Explanation for the correct answer.
    """
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)
    correct_option = Column(String(1), nullable=False)
    explanation = Column(Text)

    __table_args__ = (
        CheckConstraint("correct_option IN ('A', 'B', 'C', 'D')", name='correct_option_check'),
    )

# Create tables if they do not exist
Base.metadata.create_all(bind=engine)
logger.info("Database tables checked/created.")

# ---------------------------
# Utility Functions
# ---------------------------

def get_db_session() -> Session:
    """
    Creates and returns a new SQLAlchemy session.

    Returns:
        Session: A SQLAlchemy session object.
    """
    try:
        session = SessionLocal()
        return session
    except Exception as e:
        logger.error(f"Error creating database session: {e}")
        st.error("Database connection failed.")
        st.stop()

def fetch_all_questions(session: Session) -> list:
    """
    Retrieves all quiz questions from the database.

    Args:
        session (Session): SQLAlchemy session.

    Returns:
        list: List of Question objects.
    """
    try:
        questions = session.query(Question).all()
        logger.info(f"Fetched {len(questions)} questions from the database.")
        return questions
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        st.error("Failed to retrieve questions.")
        return []

def add_question(session: Session, question_data: dict) -> bool:
    """
    Adds a new question to the database.

    Args:
        session (Session): SQLAlchemy session.
        question_data (dict): Dictionary containing question details.

    Returns:
        bool: True if addition is successful, False otherwise.
    """
    try:
        question = Question(**question_data)
        session.add(question)
        session.commit()
        logger.info(f"Added new question with ID {question.id}.")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding question: {e}")
        return False

def parse_json_questions(json_data: str) -> list:
    """
    Parses JSON data to extract questions.

    Args:
        json_data (str): JSON string containing a list of questions.

    Returns:
        list: List of question dictionaries.
    """
    try:
        questions = json.loads(json_data)
        if isinstance(questions, list):
            logger.info(f"Parsed {len(questions)} questions from JSON data.")
            return questions
        else:
            logger.error("JSON data is not a list.")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        st.error("Invalid JSON format.")
        return []

# ---------------------------
# Streamlit Application
# ---------------------------

def main():
    """
    The main function that runs the Streamlit app.
    """
    st.set_page_config(page_title="Quiz Application", layout="wide")
    st.title("📚 Interactive Quiz Application")

    # Sidebar Navigation
    menu = ["Take Quiz", "Admin: Add Questions"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Take Quiz":
        take_quiz()
    elif choice == "Admin: Add Questions":
        admin_add_questions()

def take_quiz():
    """
    Renders the quiz-taking interface for users.
    """
    session = get_db_session()
    questions = fetch_all_questions(session)
    if not questions:
        st.warning("No questions available. Please contact the administrator.")
        return

    # Initialize session state
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    if 'answers' not in st.session_state:
        st.session_state.answers = {}
    if 'start_time' not in st.session_state:
        st.session_state.start_time = datetime.now()
    if 'time_limit' not in st.session_state:
        st.session_state.time_limit = 15  # minutes

    # Timer Logic
    elapsed_time = datetime.now() - st.session_state.start_time
    remaining_time = timedelta(minutes=st.session_state.time_limit) - elapsed_time

    if remaining_time <= timedelta(0):
        st.session_state.current_question = len(questions)  # End quiz
        st.success("Time's up! Submitting your answers...")
        submit_quiz(session, questions)
        return

    st.sidebar.write(f"⏰ Time Remaining: {str(remaining_time).split('.')[0]}")

    # Display current question
    if st.session_state.current_question < len(questions):
        question = questions[st.session_state.current_question]
        st.header(f"Question {st.session_state.current_question + 1} of {len(questions)}")
        st.write(question.question_text)

        # Display options
        options = {
            'A': question.option_a,
            'B': question.option_b,
            'C': question.option_c,
            'D': question.option_d
        }
        selected = st.radio("Select an option:", list(options.keys()), index= -1 if st.session_state.answers.get(question.id) is None else list(options.keys()).index(st.session_state.answers.get(question.id)))

        # Save answer
        if selected:
            st.session_state.answers[question.id] = selected

        # Navigation Buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Previous") and st.session_state.current_question > 0:
                st.session_state.current_question -= 1
        with col2:
            if st.button("Save for Later"):
                st.success("Your progress has been saved.")
                logger.info("User saved progress.")
        with col3:
            if st.button("Next") and st.session_state.current_question < len(questions) - 1:
                st.session_state.current_question += 1
            elif st.button("Submit") and st.session_state.current_question == len(questions) - 1:
                submit_quiz(session, questions)
    else:
        st.success("You have completed the quiz!")
        submit_quiz(session, questions)

    # Review Answers
    if st.checkbox("Review Answers"):
        review_answers(session, questions)

def submit_quiz(session: Session, questions: list):
    """
    Submits the quiz, calculates the score, and displays explanations.

    Args:
        session (Session): SQLAlchemy session.
        questions (list): List of Question objects.
    """
    score = 0
    results = []

    for question in questions:
        user_answer = st.session_state.answers.get(question.id, "No Answer")
        correct = user_answer == question.correct_option
        if correct:
            score += 1
        results.append({
            'Question': question.question_text,
            'Your Answer': f"{user_answer}: {getattr(question, f'option_{user_answer.lower()}')}" if user_answer != "No Answer" else "No Answer",
            'Correct Answer': f"{question.correct_option}: {getattr(question, f'option_{question.correct_option.lower()}')}",
            'Explanation': question.explanation,
            'Result': "Correct" if correct else "Incorrect"
        })

    st.header("🎉 Quiz Results")
    st.write(f"**Your Score:** {score} / {len(questions)}")
    df_results = pd.DataFrame(results)
    st.dataframe(df_results)

    logger.info(f"User submitted quiz with score {score}/{len(questions)}.")

def review_answers(session: Session, questions: list):
    """
    Displays a detailed review of the user's answers.

    Args:
        session (Session): SQLAlchemy session.
        questions (list): List of Question objects.
    """
    st.header("🔍 Review Your Answers")
    for idx, question in enumerate(questions, 1):
        st.subheader(f"Question {idx}: {question.question_text}")
        user_answer = st.session_state.answers.get(question.id, "No Answer")
        correct = user_answer == question.correct_option
        st.write(f"**Your Answer:** {user_answer}: {getattr(question, f'option_{user_answer.lower()}')}" if user_answer != "No Answer" else "**Your Answer:** No Answer")
        st.write(f"**Correct Answer:** {question.correct_option}: {getattr(question, f'option_{question.correct_option.lower()}')}")
        st.write(f"**Explanation:** {question.explanation}")
        st.write(f"**Result:** {'✅ Correct' if correct else '❌ Incorrect'}")
        st.markdown("---")

def admin_add_questions():
    """
    Renders the admin interface to add new questions via form or JSON upload.
    """
    st.header("🛠️ Admin Panel: Add New Questions")

    session = get_db_session()

    add_method = st.radio("Choose method to add questions:", ["Single Entry (Form)", "Bulk Entry (JSON)"])

    if add_method == "Single Entry (Form)":
        with st.form("add_question_form"):
            st.subheader("Add a New Question")

            question_text = st.text_area("Question Text", max_chars=500, help="Enter the question.")

            option_a = st.text_input("Option A", max_chars=100)
            option_b = st.text_input("Option B", max_chars=100)
            option_c = st.text_input("Option C", max_chars=100)
            option_d = st.text_input("Option D", max_chars=100)

            correct_option = st.selectbox("Correct Option", ["A", "B", "C", "D"], help="Select the correct option.")

            explanation = st.text_area("Explanation", max_chars=500, help="Provide an explanation for the correct answer.")

            submitted = st.form_submit_button("Add Question")

            if submitted:
                question_data = {
                    'question_text': question_text,
                    'option_a': option_a,
                    'option_b': option_b,
                    'option_c': option_c,
                    'option_d': option_d,
                    'correct_option': correct_option,
                    'explanation': explanation
                }

                if all([question_text, option_a, option_b, option_c, option_d, correct_option]):
                    success = add_question(session, question_data)
                    if success:
                        st.success("Question added successfully!")
                    else:
                        st.error("Failed to add question. Check logs for details.")
                else:
                    st.error("Please fill in all fields.")

    elif add_method == "Bulk Entry (JSON)":
        uploaded_file = st.file_uploader("Upload JSON File", type=["json"], help="Upload a JSON file containing questions.")
        if uploaded_file is not None:
            try:
                json_data = uploaded_file.read().decode('utf-8')
                questions = parse_json_questions(json_data)
                if questions:
                    success_count = 0
                    for q in questions:
                        # Validate required fields
                        required_fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option', 'explanation']
                        if all(field in q for field in required_fields):
                            success = add_question(session, q)
                            if success:
                                success_count += 1
                        else:
                            logger.warning(f"Question missing fields: {q}")
                    st.success(f"Successfully added {success_count} questions.")
            except Exception as e:
                logger.error(f"Error processing uploaded file: {e}")
                st.error("Failed to process the uploaded file.")

if __name__ == "__main__":
    main()