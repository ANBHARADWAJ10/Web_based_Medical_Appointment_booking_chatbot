import os
import json
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

# contact
import re
# Load environment variables
load_dotenv()

# MongoDB imports
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# NLP imports - Fixed NLTK import and download issues
import nltk

# Download required NLTK data with proper error handling
def download_nltk_data():
    """Download NLTK data with fallback for different NLTK versions"""
    try:
        # Try to download punkt_tab (for NLTK 3.8.2+)
        try:
            nltk.download('punkt_tab', quiet=True)
            print("✅ Downloaded punkt_tab successfully")
        except:
            # Fallback to punkt (for older NLTK versions)
            try:
                nltk.download('punkt', quiet=True)
                print("✅ Downloaded punkt successfully")
            except Exception as e:
                print(f"⚠️  Warning: Could not download punkt tokenizer: {e}")
        
        # Download other required packages
        try:
            nltk.download('stopwords', quiet=True)
            print("✅ Downloaded stopwords successfully")
        except Exception as e:
            print(f"⚠️  Warning: Could not download stopwords: {e}")
        
        try:
            nltk.download('wordnet', quiet=True)
            print("✅ Downloaded wordnet successfully")
        except Exception as e:
            print(f"⚠️  Warning: Could not download wordnet: {e}")
            
    except Exception as e:
        print(f"⚠️  Warning: NLTK download failed: {e}")
        print("📝 Note: You may need to download NLTK data manually")

# Initialize NLTK downloads
download_nltk_data()

# Import NLTK components with fallbacks
try:
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    from nltk.stem import WordNetLemmatizer
    NLTK_AVAILABLE = True
    print("✅ NLTK components loaded successfully")
except ImportError as e:
    print(f"⚠️  Warning: NLTK components not available: {e}")
    NLTK_AVAILABLE = False

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
CORS(app)

# Environment variables
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')

class MedicalChatBot:
    def __init__(self):
        # MongoDB connection setup
        try:
            self.mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.db = self.mongo_client['testDb']
            self.dates_collection = self.db['dates']
            self.doctors_collection = self.db['doctors']
            self.patients_collection = self.db['patients']
            self.confirmations_collection = self.db['confirmations']
            
            # Test the connection
            self.mongo_client.admin.command('ping')
            logger.info("✅ Successfully connected to MongoDB")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            # Create mock collections for testing without MongoDB
            print("📝 Running in demo mode without MongoDB")
            self.mongo_client = None
            self.db = None
        
        # In-memory storage for web sessions
        self.user_sessions = {}
        self.booked_slots = {}
        
        # Blood groups
        self.blood_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
        
        # Initialize NLP components with fallbacks
        if NLTK_AVAILABLE:
            try:
                self.lemmatizer = WordNetLemmatizer()
                self.stop_words = set(stopwords.words('english'))
                print("✅ NLP components initialized successfully")
            except Exception as e:
                print(f"⚠️  Warning: Could not initialize NLP components: {e}")
                self.lemmatizer = None
                self.stop_words = set()
        else:
            self.lemmatizer = None
            self.stop_words = set()
        
        # Symptom-Disease mapping
        self.symptom_disease_map = {
            'fever': ['Viral Infection', 'Bacterial Infection', 'Flu'],
            'headache': ['Migraine', 'Tension Headache', 'Sinusitis'],
            'cough': ['Common Cold', 'Bronchitis', 'Pneumonia'],
            'blocked': ['Common Cold', 'Allergic Rhinitis', 'Sinusitis'],
            'nose': ['Common Cold', 'Allergic Rhinitis', 'Sinusitis'],
            'sore': ['Viral Pharyngitis', 'Strep Throat', 'Common Cold'],
            'throat': ['Viral Pharyngitis', 'Strep Throat', 'Common Cold'],
            'body': ['Flu', 'Viral Infection', 'Muscle Strain'],
            'pain': ['Flu', 'Viral Infection', 'Muscle Strain'],
            'nausea': ['Food Poisoning', 'Gastroenteritis', 'Migraine'],
            'vomiting': ['Food Poisoning', 'Gastroenteritis', 'Viral Infection'],
            'diarrhea': ['Food Poisoning', 'Gastroenteritis', 'IBS'],
            'fatigue': ['Viral Infection', 'Anemia', 'Chronic Fatigue'],
            'chest': ['Acid Reflux', 'Muscle Strain', 'Anxiety'],
            'shortness': ['Asthma', 'Anxiety', 'Respiratory Infection'],
            'breath': ['Asthma', 'Anxiety', 'Respiratory Infection'],
            'cold': ['Common Cold', 'Viral Infection'],
            'runny': ['Common Cold', 'Allergic Rhinitis'],
            'sneezing': ['Common Cold', 'Allergic Rhinitis'],
            'weakness': ['Viral Infection', 'Anemia', 'Dehydration']
        }

        # Mock data for demo mode
        self.mock_doctors = [
            {
                '_id': '1',
                'name': 'Dr. Sarah Johnson',
                'firstName': 'Sarah',
                'lastName': 'Johnson',
                'specialty': 'General Medicine',
                'qualification': 'MBBS, MD',
                'availability': 'Mon-Fri 9AM-5PM'
            },
            {
                '_id': '2',
                'name': 'Dr. Michael Chen',
                'firstName': 'Michael',
                'lastName': 'Chen',
                'specialty': 'Cardiology',
                'qualification': 'MBBS, DM Cardiology',
                'availability': 'Mon-Wed 10AM-4PM'
            },
            {
                '_id': '3',
                'name': 'Dr. Emily Davis',
                'firstName': 'Emily',
                'lastName': 'Davis',
                'specialty': 'Pediatrics',
                'qualification': 'MBBS, MD Pediatrics',
                'availability': 'Tue-Sat 8AM-6PM'
            }
        ]

    def generate_unique_code(self):
        """Generate 8-digit unique code"""
        while True:
            code = ''.join(random.choices(string.digits, k=8))
            # In demo mode, just return the code
            if not self.mongo_client:
                return code
            # Check if code already exists in patients collection
            try:
                existing_patient = self.patients_collection.find_one({"uniqueCode": code})
                if not existing_patient:
                    return code
            except:
                return code

    def get_booking_details_by_code(self, unique_code):
        """Get complete booking details by unique code"""
        if not self.mongo_client:
            # Demo mode - return mock data
            return {
                "uniqueCode": unique_code,
                "patient": {
                    "name": "John Doe",
                    "age": "30",
                    "gender": "Male",
                    "blood": "B+",
                    "contact": "+1234567890",
                },
                "doctor": {
                    "name": "Dr. Sarah Johnson",
                    "specialty": "General Medicine",
                },
                "appointment": {
                    "date": "10/15/2025",
                    "status": "confirmed",
                    "createdAt": datetime.now().isoformat(),
                },
                "confirmationId": "demo123",
                "patientId": "demo456"
            }
        
        try:
            # Find patient by unique code
            patient = self.patients_collection.find_one({"uniqueCode": unique_code})
            if not patient:
                return None

            # Find confirmation for this patient
            confirmation = self.confirmations_collection.find_one({"patient": patient["_id"]})
            if not confirmation:
                return None

            # Get doctor details if doctor ID exists
            doctor_name = confirmation.get("doctorName", "N/A")
            doctor_specialty = "N/A"
            if confirmation.get("doctor"):
                doctor = self.doctors_collection.find_one({"_id": confirmation["doctor"]})
                if doctor:
                    doctor_specialty = doctor.get("specialty", "N/A")

            # Format the booking details
            booking_details = {
                "uniqueCode": unique_code,
                "patient": {
                    "name": patient.get("name", ""),
                    "age": patient.get("age", ""),
                    "gender": patient.get("gender", ""),
                    "blood": patient.get("blood", ""),
                    "contact": patient.get("contact", ""),
                },
                "doctor": {
                    "name": doctor_name,
                    "specialty": doctor_specialty,
                },
                "appointment": {
                    "date": confirmation.get("date", ""),
                    "status": confirmation.get("status", ""),
                    "createdAt": confirmation.get("createdAt", ""),
                },
                "confirmationId": str(confirmation.get("_id", "")),
                "patientId": str(patient.get("_id", ""))
            }

            return booking_details
        except Exception as e:
            logger.error(f"Error fetching booking details: {e}")
            return None

    def save_patient_to_db(self, patient_data, unique_code):
        """Save patient information to MongoDB patients collection with unique code"""
        if not self.mongo_client:
            # Demo mode
            return "demo_patient_id"
        
        try:
            patient_document = {
                "name": patient_data.get('name', ''),
                "age": int(patient_data.get('age', 0)),
                "gender": patient_data.get('gender', ''),
                "blood": patient_data.get('blood_group', ''),
                "contact": patient_data.get('contact', ''),
                "uniqueCode": unique_code,
                "symptoms": patient_data.get('symptoms', []),
                "matchedSymptoms": patient_data.get('matched_symptoms', []),
                "possibleDiseases": patient_data.get('possible_diseases', []),
                "createdAt": datetime.now(),
                "updatedAt": datetime.now()
            }

            result = self.patients_collection.insert_one(patient_document)
            logger.info(f"Patient saved successfully with ID: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Error saving patient: {e}")
            return None

    def save_confirmation_to_db(self, patient_id, confirmation_data, unique_code):
        """Save appointment confirmation to MongoDB confirmations collection with unique code"""
        if not self.mongo_client:
            # Demo mode
            return "demo_confirmation_id"
        
        try:
            confirmation_document = {
                "patient": patient_id,
                "doctor": confirmation_data.get('doctor_id'),
                "doctorName": confirmation_data.get('doctor_name', ''),
                "date": confirmation_data.get('appointment_date'),
                "slot": confirmation_data.get('selected_slot', ''),
                "status": confirmation_data.get('status', 'confirmed'),
                "uniqueCode": unique_code,
                "createdAt": datetime.now(),
                "updatedAt": datetime.now()
            }

            result = self.confirmations_collection.insert_one(confirmation_document)
            logger.info(f"Confirmation saved successfully with ID: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Error saving confirmation: {e}")
            return None

    def complete_booking_process(self, session_data, slot_data):
        """Complete booking process by saving both patient and confirmation data with unique code"""
        try:
            patient_data = session_data['patient_data']
            
            # Generate unique code
            unique_code = self.generate_unique_code()
            
            # Step 1: Save patient information with unique code
            patient_id = self.save_patient_to_db(patient_data, unique_code)
            if not patient_id:
                return False, "Failed to save patient information"

            # Step 2: Prepare confirmation data
            confirmation_data = {
                'doctor_id': patient_data.get('selected_doctor', {}).get('_id'),
                'doctor_name': patient_data.get('selected_doctor', {}).get('name', ''),
                'appointment_date': patient_data.get('selected_date'),
                'appointment_time': patient_data.get('selected_time', ''),
                'selected_slot': patient_data.get('selected_slot', ''),
                'status': 'confirmed'
            }

            # Step 3: Save confirmation with unique code
            confirmation_id = self.save_confirmation_to_db(patient_id, confirmation_data, unique_code)
            if not confirmation_id:
                return False, "Failed to save confirmation"

            return True, {
                "patient_id": patient_id,
                "confirmation_id": confirmation_id,
                "unique_code": unique_code
            }
        except Exception as e:
            logger.error(f"Error in complete booking process: {e}")
            return False, f"Booking failed: {str(e)}"

    def get_available_doctors(self):
        """Get list of available doctors from MongoDB"""
        if not self.mongo_client:
            # Return mock doctors for demo
            return self.mock_doctors
        
        try:
            doctors_cursor = self.doctors_collection.find({"isDeleted": False})
            doctors = []
            for doc in doctors_cursor:
                doctor_info = {
                    '_id': str(doc.get('_id')),
                    'name': doc.get('name', ''),
                    'firstName': doc.get('firstName', ''),
                    'lastName': doc.get('lastName', ''),
                    'specialty': doc.get('specialty', ''),
                    'qualification': doc.get('qualification', ''),
                    'availability': doc.get('availability', '')
                }
                doctors.append(doctor_info)
            
            logger.info(f"Found {len(doctors)} available doctors")
            return doctors
        except Exception as e:
            logger.error(f"Error fetching doctors: {e}")
            return self.mock_doctors  # Fallback to mock data

    def parse_date_from_db(self, date_str):
        """Parse date string from database into datetime object"""
        try:
            date_formats = ["%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"]
            for date_format in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, date_format)
                    logger.debug(f"Successfully parsed '{date_str}' with format '{date_format}' -> {parsed_date}")
                    return parsed_date
                except ValueError:
                    continue
            logger.warning(f"Could not parse date: {date_str}")
            return None
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return None

    def get_next_7_upcoming_dates(self, doctor_availability=None):
        """Get the next 7 upcoming dates"""
        if not self.mongo_client:
            # Generate mock dates for demo
            mock_dates = []
            current_date = datetime.now()
            for i in range(7):
                date = current_date + timedelta(days=i+1)
                mock_dates.append({
                    'date': date.strftime("%m-%d-%Y"),
                    'date_obj': date,
                    'display_name': f"{date.strftime('%A')}, {date.strftime('%B %d, %Y')}",
                    'time_slots': [
                        {'time': '9:00 AM', 'is_booked': False},
                        {'time': '10:00 AM', 'is_booked': False},
                        {'time': '11:00 AM', 'is_booked': False},
                        {'time': '2:00 PM', 'is_booked': False},
                        {'time': '3:00 PM', 'is_booked': False}
                    ],
                    'total_available_slots': 5
                })
            return mock_dates
        
        try:
            logger.info("Fetching upcoming dates from MongoDB...")
            
            # Get current date
            current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            logger.info(f"Current date: {current_date}")
            
            # Fetch all documents from MongoDB
            dates_cursor = self.dates_collection.find({})
            all_docs = list(dates_cursor)
            logger.info(f"Found {len(all_docs)} documents in dates collection")
            
            # Group documents by date and collect all times for each date
            dates_map = {}
            processed_count = 0
            
            for doc in all_docs:
                date_str = doc.get('date', '')
                time_str = doc.get('time', '')
                logger.debug(f"Processing doc: date='{date_str}', time='{time_str}'")
                
                if not date_str or not time_str:
                    logger.warning(f"Skipping doc with missing date/time: {doc}")
                    continue
                
                # Parse the date
                parsed_date = self.parse_date_from_db(date_str)
                if not parsed_date:
                    logger.warning(f"Could not parse date: {date_str}")
                    continue
                
                # Skip past dates
                if parsed_date < current_date:
                    logger.debug(f"Skipping past date: {parsed_date}")
                    continue
                
                processed_count += 1
                
                # Create standardized date key
                date_key = parsed_date.strftime("%m-%d-%Y")
                
                # Initialize date entry if not exists
                if date_key not in dates_map:
                    dates_map[date_key] = {
                        'date': date_key,
                        'date_obj': parsed_date,
                        'display_name': f"{parsed_date.strftime('%A')}, {parsed_date.strftime('%B %d, %Y')}",
                        'time_slots': [],
                        'total_available_slots': 0
                    }
                
                # Add time slot
                dates_map[date_key]['time_slots'].append({
                    'time': time_str,
                    'is_booked': False  # Simplified for web version
                })
                dates_map[date_key]['total_available_slots'] += 1
            
            # Get first 7 dates with available slots
            available_dates = []
            sorted_dates = sorted(dates_map.keys(), key=lambda x: dates_map[x]['date_obj'])
            
            for date_key in sorted_dates:
                if dates_map[date_key]['total_available_slots'] > 0:
                    available_dates.append(dates_map[date_key])
                    if len(available_dates) >= 7:
                        break
            
            logger.info(f"Returning {len(available_dates)} available dates")
            return available_dates
        except Exception as e:
            logger.error(f"Error fetching upcoming dates: {e}")
            return []

    def preprocess_symptoms(self, text):
        """Preprocess symptoms text using NLP with fallbacks"""
        text = text.lower()
        
        if not NLTK_AVAILABLE or not self.lemmatizer:
            # Simple fallback without NLTK
            words = text.split()
            # Basic stopwords
            basic_stopwords = {'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once'}
            
            processed_tokens = []
            for word in words:
                if word not in basic_stopwords and word.isalpha():
                    processed_tokens.append(word)
            return processed_tokens
        
        try:
            tokens = word_tokenize(text)
        except Exception as e:
            logger.warning(f"Tokenization error: {e}")
            tokens = text.split()
        
        processed_tokens = []
        for token in tokens:
            if token not in self.stop_words and token.isalpha():
                try:
                    lemmatized = self.lemmatizer.lemmatize(token)
                    processed_tokens.append(lemmatized)
                except Exception as e:
                    logger.warning(f"Lemmatization error: {e}")
                    processed_tokens.append(token)
        
        return processed_tokens

    def analyze_symptoms(self, symptoms_list):
        """Analyze symptoms and predict possible diseases"""
        all_symptoms_text = " ".join(symptoms_list)
        processed_symptoms = self.preprocess_symptoms(all_symptoms_text)
        
        matched_symptoms = []
        possible_diseases = set()
        
        for token in processed_symptoms:
            if token in self.symptom_disease_map:
                matched_symptoms.append(token)
                possible_diseases.update(self.symptom_disease_map[token])
        
        # Special handling for common combinations
        symptoms_lower = all_symptoms_text.lower()
        if 'blocked nose' in symptoms_lower or 'stuffy nose' in symptoms_lower:
            matched_symptoms.append('blocked_nose')
            possible_diseases.update(['Common Cold', 'Allergic Rhinitis', 'Sinusitis'])
        
        if 'sore throat' in symptoms_lower:
            matched_symptoms.append('sore_throat')
            possible_diseases.update(['Viral Pharyngitis', 'Strep Throat', 'Common Cold'])
        
        if 'body pain' in symptoms_lower or 'body ache' in symptoms_lower:
            matched_symptoms.append('body_pain')
            possible_diseases.update(['Flu', 'Viral Infection', 'Muscle Strain'])
        
        return list(set(matched_symptoms)), list(possible_diseases)

# Initialize bot
bot = MedicalChatBot()

# Flask Routes
@app.route('/')
def index():
    """Serve the main chat interface"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.json
        message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Initialize session if not exists
        if session_id not in bot.user_sessions:
            bot.user_sessions[session_id] = {
                'state': 'greeting',
                'patient_data': {},
                'conversation_history': []
            }
        
        session = bot.user_sessions[session_id]
        response = process_message(message, session)
        
        # Add to conversation history
        session['conversation_history'].append({
            'user': message,
            'bot': response['message'],
            'timestamp': datetime.now().isoformat()
        })
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/check-booking', methods=['POST'])
def check_booking():
    """Check booking details by unique code"""
    try:
        data = request.json
        unique_code = data.get('code', '').strip()
        
        if len(unique_code) != 8 or not unique_code.isdigit():
            return jsonify({'error': 'Invalid code format. Please enter an 8-digit code.'}), 400
        
        booking_details = bot.get_booking_details_by_code(unique_code)
        
        if booking_details:
            return jsonify({
                'success': True,
                'booking_details': booking_details
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Code not found. Please check your code and try again.'
            })
            
    except Exception as e:
        logger.error(f"Error checking booking: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    """Get available doctors"""
    try:
        doctors = bot.get_available_doctors()
        return jsonify({'doctors': doctors})
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return jsonify({'error': 'Error fetching doctors'}), 500

@app.route('/api/dates', methods=['GET'])
def get_dates():
    """Get available dates"""
    try:
        doctor_availability = request.args.get('doctor_availability')
        dates = bot.get_next_7_upcoming_dates(doctor_availability)
        return jsonify({'dates': dates})
    except Exception as e:
        logger.error(f"Error fetching dates: {e}")
        return jsonify({'error': 'Error fetching dates'}), 500

def process_message(message, session):
    """Process user message based on current state"""
    current_state = session.get('state', 'greeting')
    
    # Handle session reset
    if message.lower() == 'reset_to_menu':
        session['state'] = 'greeting'
        session['patient_data'] = {}
        return {
            'message': '🏥 Back to Main Menu! 🏥\n\nI can help you with:\n• Check your existing booking details with unique code\n• Book a new doctor\'s appointment\n\nPlease select an option below:',
            'type': 'menu'
        }
    
    # Handle menu reset
    if message.lower() in ['menu', 'main menu', 'back', 'start over']:
        session['state'] = 'greeting'
        session['patient_data'] = {}
        return handle_greeting('menu', session)
    
    # Handle end command with confirmation
    if message.lower() == 'end':
        return {
            'message': 'Are you sure you want to go back to the main menu? This will end your current session.',
            'type': 'end_confirmation'
        }
    
    if current_state == 'greeting':
        return handle_greeting(message, session)
    elif current_state == 'waiting_code':
        return handle_code_input(message, session)
    elif current_state == 'booking_start':
        return handle_booking_start(message, session)
    elif current_state == 'waiting_name':
        return handle_name_input(message, session)
    elif current_state == 'waiting_blood_group':
        return handle_blood_group_input(message, session)
    elif current_state == 'waiting_age':
        return handle_age_input(message, session)
    elif current_state == 'waiting_gender':
        return handle_gender_input(message, session)
    elif current_state == 'waiting_contact':
        return handle_contact_input(message, session)
    elif current_state == 'waiting_symptoms':
        return handle_symptoms_input(message, session)
    elif current_state == 'waiting_doctor_selection':
        return handle_doctor_selection(message, session)
    elif current_state == 'waiting_date_selection':
        return handle_date_selection(message, session)
    elif current_state == 'waiting_time_selection':
        return handle_time_selection(message, session)
    else:
        return handle_greeting(message, session)


def handle_greeting(message, session):
    """Handle initial greeting and menu selection"""
    message_lower = message.lower()
    
    if 'check' in message_lower and 'booking' in message_lower:
        session['state'] = 'waiting_code'
        return {
            'message': '🔑 Please enter your 8-digit unique code to access your booking details:',
            'type': 'text_input',
            'placeholder': 'Enter 8-digit code'
        }
    elif 'book' in message_lower and 'appointment' in message_lower:
        session['state'] = 'waiting_name'
        session['patient_data'] = {}
        return {
            'message': '👤 Great! Let\'s book your appointment. Please enter your full name:',
            'type': 'text_input',
            'placeholder': 'Enter your full name'
        }
    else:
        return {
            'message': '🏥 Welcome to Medical Chatbot! 🏥\n\nI can help you with:\n• Check your existing booking details with unique code\n• Book a new doctor\'s appointment\n\nPlease select an option below:',
            'type': 'menu'
        }

def handle_code_input(message, session):
    """Handle booking code verification"""
    code = message.strip()
    
    if len(code) != 8 or not code.isdigit():
        return {
            'message': '❌ Invalid code format. Please enter an 8-digit code:',
            'type': 'text_input',
            'placeholder': 'Enter 8-digit code'
        }
    
    booking_details = bot.get_booking_details_by_code(code)
    
    if booking_details:
        session['state'] = 'greeting'  # Reset to main menu
        details_text = f"📋 **Booking Details:**\n\n"
        details_text += f"🔑 **Unique Code:** {booking_details['uniqueCode']}\n\n"
        details_text += f"👤 **Patient Information:**\n"
        details_text += f"• Name: {booking_details['patient']['name']}\n"
        details_text += f"• Age: {booking_details['patient']['age']}\n"
        details_text += f"• Gender: {booking_details['patient']['gender']}\n"
        details_text += f"• Blood Group: {booking_details['patient']['blood']}\n"
        details_text += f"• Contact: {booking_details['patient']['contact']}\n\n"
        details_text += f"👨‍⚕️ **Doctor Information:**\n"
        details_text += f"• Doctor: {booking_details['doctor']['name']}\n"
        details_text += f"• Specialty: {booking_details['doctor']['specialty']}\n\n"
        details_text += f"📅 **Appointment Details:**\n"
        details_text += f"• Date: {booking_details['appointment']['date']}\n"
        details_text += f"• Status: {booking_details['appointment']['status'].title()}\n\n"
        details_text += "You can type 'menu' to return to main menu."
        
        return {
            'message': details_text,
            'type': 'booking_details'
        }
    else:
        return {
            'message': '❌ Code not found. Please check your code and try again.\n\nType "menu" to return to main menu.',
            'type': 'error'
        }

def handle_name_input(message, session):
    """Handle name input for booking"""
    name = message.strip()
    session['patient_data']['name'] = name
    session['state'] = 'waiting_blood_group'
    
    return {
        'message': f'Hello {name}! 🩸 Please select your blood group:',
        'type': 'blood_group_selection',
        'options': bot.blood_groups
    }

def handle_blood_group_input(message, session):
    """Handle blood group selection"""
    blood_group = message.strip().upper()
    
    if blood_group not in bot.blood_groups:
        return {
            'message': f'🩸 Please select your blood group from the options below:',
            'type': 'blood_group_selection',
            'options': bot.blood_groups
        }
    
    session['patient_data']['blood_group'] = blood_group
    session['state'] = 'waiting_age'
    
    return {
        'message': f'🩸 Blood Group: {blood_group}\n\n📅 Please enter your age:',
        'type': 'text_input',
        'placeholder': 'Enter your age'
    }

def handle_age_input(message, session):
    """Handle age input"""
    age = message.strip()
    
    if not age.isdigit() or int(age) < 1 or int(age) > 120:
        return {
            'message': '❌ Please enter a valid age (1-120):',
            'type': 'text_input',
            'placeholder': 'Enter your age'
        }
    
    session['patient_data']['age'] = age
    session['state'] = 'waiting_gender'
    
    return {
        'message': f'📅 Age: {age}\n\n⚧ Please select your gender:',
        'type': 'gender_selection',
        'options': ['Male', 'Female', 'Other']
    }

def handle_gender_input(message, session):
    """Handle gender input"""
    gender = message.strip().capitalize()
    
    if gender not in ['Male', 'Female', 'Other']:
        return {
            'message': '⚧ Please select your gender:',
            'type': 'gender_selection',
            'options': ['Male', 'Female', 'Other']
        }
    
    session['patient_data']['gender'] = gender
    session['state'] = 'waiting_contact'
    
    return {
        'message': f'⚧ Gender: {gender}\n\n📞 Please enter your contact number:',
        'type': 'text_input',
        'placeholder': 'Enter your contact number'
    }

# def handle_contact_input(message, session):
#     """Handle contact input"""
#     contact = message.strip()
#     session['patient_data']['contact'] = contact
#     session['patient_data']['symptoms'] = []
#     session['state'] = 'waiting_symptoms'
    
#     return {
#         'message': f'📞 Contact: {contact}\n\n🩺 Please describe your symptoms (e.g., fever, headache, blocked nose, cough):\n\nYou can type multiple symptoms separated by commas.',
#         'type': 'text_input',
#         'placeholder': 'Describe your symptoms'
#     }

def handle_contact_input(message, session):
    """Handle contact input with Indian mobile number validation"""
    contact = message.strip()

    # Indian mobile number regex:
    # Optional +91 / 91 / 0 prefix and 10 digits starting with 6–9
    pattern = r'^(?:\+91|91|0)?[6-9]\d{9}$'

    # Validate number
    if not re.match(pattern, contact):
        return {
            'message': '❌ Invalid mobile number.\n\nPlease enter a valid Indian mobile number (e.g., 9876543210 or +919876543210):',
            'type': 'text_input',
            'placeholder': 'Enter your contact number'
        }

    # Normalize to last 10 digits
    contact = contact[-10:]

    # Save valid contact and continue
    session['patient_data']['contact'] = contact
    session['patient_data']['symptoms'] = []
    session['state'] = 'waiting_symptoms'

    return {
        'message': f'📞 Contact: {contact}\n\n🩺 Please describe your symptoms (e.g., fever, headache, blocked nose, cough):\n\nYou can type multiple symptoms separated by commas.',
        'type': 'text_input',
        'placeholder': 'Describe your symptoms'
    }

def handle_symptoms_input(message, session):
    """Handle symptoms input"""
    symptoms_text = message.strip()
    symptoms = [s.strip() for s in symptoms_text.split(',') if s.strip()]
    session['patient_data']['symptoms'].extend(symptoms)
    
    # Analyze symptoms
    matched_symptoms, possible_diseases = bot.analyze_symptoms(session['patient_data']['symptoms'])
    session['patient_data']['matched_symptoms'] = matched_symptoms
    session['patient_data']['possible_diseases'] = possible_diseases
    
    # Get available doctors
    doctors = bot.get_available_doctors()
    session['available_doctors'] = doctors
    session['state'] = 'waiting_doctor_selection'
    
    analysis_text = f"✅ Recorded symptoms: {', '.join(symptoms)}\n\n"
    analysis_text += f"🔍 **Pre-Analysis Results:**\n"
    analysis_text += f"📝 **Your Symptoms:** {', '.join(session['patient_data']['symptoms'])}\n"
    analysis_text += f"🧪 **Matched Symptoms:** {', '.join(matched_symptoms) if matched_symptoms else 'General symptoms detected'}\n\n"
    analysis_text += "👨‍⚕️ **Available Doctors:**\n"
    analysis_text += "Please select a doctor from the options below:"
    
    return {
        'message': analysis_text,
        'type': 'doctor_selection',
        'doctors': doctors
    }

def handle_doctor_selection(message, session):
    """Handle doctor selection"""
    try:
        doctor_index = int(message.strip()) - 1
        doctors = session.get('available_doctors', [])
        
        if 0 <= doctor_index < len(doctors):
            selected_doctor = doctors[doctor_index]
            session['patient_data']['selected_doctor'] = selected_doctor
            session['state'] = 'waiting_date_selection'
            
            # Get available dates
            dates = bot.get_next_7_upcoming_dates(selected_doctor.get('availability'))
            session['available_dates'] = dates
            
            response_text = f"👨‍⚕️ **Selected Doctor:** {selected_doctor['name']}\n"
            response_text += f"🏥 **Specialty:** {selected_doctor['specialty']}\n"
            response_text += f"🕐 **Availability:** {selected_doctor['availability']}\n\n"
            response_text += "📅 **Available Appointment Dates:**\n"
            response_text += "Please select a date from the options below:"
            
            return {
                'message': response_text,
                'type': 'date_selection',
                'dates': dates
            }
        else:
            return {
                'message': '❌ Invalid selection. Please select a doctor from the options below:',
                'type': 'doctor_selection',
                'doctors': session.get('available_doctors', [])
            }
    except ValueError:
        return {
            'message': '❌ Please select a doctor from the options below:',
            'type': 'doctor_selection',
            'doctors': session.get('available_doctors', [])
        }

def handle_date_selection(message, session):
    """Handle date selection"""
    try:
        date_index = int(message.strip()) - 1
        dates = session.get('available_dates', [])
        
        if 0 <= date_index < len(dates):
            selected_date_info = dates[date_index]
            session['patient_data']['selected_date'] = selected_date_info['date']
            session['patient_data']['selected_date_display'] = selected_date_info['display_name']
            session['state'] = 'waiting_time_selection'
            
            # Get available time slots for selected date
            time_slots = selected_date_info['time_slots']
            session['available_time_slots'] = time_slots
            
            response_text = f"📅 **Selected Date:** {selected_date_info['display_name']}\n\n"
            response_text += "🕐 **Available Time Slots:**\n"
            response_text += "Please select a time slot from the options below:"
            
            return {
                'message': response_text,
                'type': 'time_selection',
                'time_slots': time_slots
            }
        else:
            return {
                'message': '❌ Invalid selection. Please select a date from the options below:',
                'type': 'date_selection',
                'dates': session.get('available_dates', [])
            }
    except ValueError:
        return {
            'message': '❌ Please select a date from the options below:',
            'type': 'date_selection',
            'dates': session.get('available_dates', [])
        }

def handle_time_selection(message, session):
    """Handle time slot selection and complete booking"""
    try:
        time_index = int(message.strip()) - 1
        time_slots = session.get('available_time_slots', [])
        
        if 0 <= time_index < len(time_slots):
            selected_time_slot = time_slots[time_index]
            session['patient_data']['selected_time'] = selected_time_slot['time']
            session['patient_data']['selected_slot'] = selected_time_slot['time']
            
            # Complete booking process
            success, result = bot.complete_booking_process(session, {})
            
            if success:
                patient_data = session['patient_data']
                doctor_info = patient_data.get('selected_doctor')
                unique_code = result['unique_code']
                
                confirmation_message = f"✅ **Appointment Confirmed!**\n\n"
                confirmation_message += f"🔑 **Your Unique Code:** {unique_code}\n"
                confirmation_message += f"*Save this code to check your booking details anytime*\n\n"
                confirmation_message += f"👤 **Patient:** {patient_data['name']}\n"
                confirmation_message += f"📞 **Contact:** {patient_data['contact']}\n"
                confirmation_message += f"🩺 **Doctor:** {doctor_info['name']}\n"
                confirmation_message += f"📅 **Date:** {patient_data['selected_date_display']}\n"
                confirmation_message += f"🕐 **Time Slot:** {selected_time_slot['time']}\n\n"
                confirmation_message += f"Thank you for booking with us! Use your unique code {unique_code} to check details anytime.\n\n"
                confirmation_message += "Type 'menu' to return to main menu for new booking."
                
                # Reset session
                session['state'] = 'greeting'
                session['patient_data'] = {}
                
                return {
                    'message': confirmation_message,
                    'type': 'booking_confirmed',
                    'unique_code': unique_code
                }
            else:
                return {
                    'message': f"❌ **Booking Failed**\n\n{result}\n\nPlease try again or contact support.\n\nType 'menu' to return to main menu.",
                    'type': 'error'
                }
        else:
            return {
                'message': '❌ Invalid selection. Please select a time slot from the options below:',
                'type': 'time_selection',
                'time_slots': session.get('available_time_slots', [])
            }
    except ValueError:
        return {
            'message': '❌ Please select a time slot from the options below:',
            'type': 'time_selection',
            'time_slots': session.get('available_time_slots', [])
        }

if __name__ == '__main__':
    print("🏥 Medical Web Chatbot is starting...")
    print("📝 NLTK Status:", "✅ Available" if NLTK_AVAILABLE else "⚠️  Limited (using fallbacks)")
    print("💾 MongoDB Status:", "✅ Connected" if bot.mongo_client else "⚠️  Demo Mode")
    print("🌐 Server running at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS