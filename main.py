import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
import os
import asyncio

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
WEBSITE_URL = "https://rtdc.tourism.rajasthan.gov.in"

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

class QABot:
    def __init__(self):
        self.website_data = None
    
    def scrape_website_data(self):
        """Website se latest data scrape kare"""
        try:
            logger.info("Scraping website data...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(WEBSITE_URL, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # All relevant data collect karein
            data = {
                'page_title': soup.title.text.strip() if soup.title else "Rajasthan Tourism",
                'headings': [],
                'paragraphs': [],
                'links': [],
                'metadata': []
            }
            
            # Headings
            for tag in ['h1', 'h2', 'h3', 'h4']:
                for heading in soup.find_all(tag):
                    text = heading.get_text().strip()
                    if text and len(text) > 5:
                        data['headings'].append(text)
            
            # Paragraphs
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if text and len(text) > 20:
                    data['paragraphs'].append(text)
            
            # Important links
            for a in soup.find_all('a', href=True):
                text = a.get_text().strip()
                if text and len(text) > 3:
                    href = a['href']
                    if href.startswith('/'):
                        href = WEBSITE_URL + href
                    elif not href.startswith('http'):
                        href = WEBSITE_URL + '/' + href
                    data['links'].append(f"{text}: {href}")
            
            self.website_data = data
            logger.info(f"Scraped {len(data['headings'])} headings, {len(data['paragraphs'])} paragraphs")
            return data
            
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return None
    
    async def get_ai_response(self, question, website_data):
        """Gemini ko question + website data bhejke answer milega"""
        try:
            # Prompt prepare karein
            prompt = f"""
            User ka question: "{question}"
            
            Rajasthan Tourism website ka latest data:
            PAGE TITLE: {website_data['page_title']}
            
            HEADINGS:
            {chr(10).join(['- ' + heading for heading in website_data['headings'][:15]])}
            
            IMPORTANT CONTENT:
            {chr(10).join(['- ' + para for para in website_data['paragraphs'][:10]])}
            
            LINKS:
            {chr(10).join(['- ' + link for link in website_data['links'][:10]])}
            
            Instructions:
            1. Sirf diye gaye website data ke according answer do
            2. Agar information nahi hai to clearly batao
            3. Hindi me answer do (unless user English me puchen)
            4. Short aur clear answers do
            5. Relevant links include karo agar available hon
            
            Answer:
            """
            
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"AI response error: {e}")
            return f"❌ Error processing your question: {str(e)}"
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """User ke message ko handle kare"""
        user_message = update.message.text
        user = update.effective_user
        
        logger.info(f"User {user.first_name} asked: {user_message}")
        
        # Typing indicator bheje
        await update.message.chat.send_action(action="typing")
        
        try:
            # Pehle website se latest data lao
            website_data = await asyncio.get_event_loop().run_in_executor(None, self.scrape_website_data)
            
            if not website_data:
                await update.message.reply_text("❌ Website se data fetch nahi kar pa raha. Kuch der baad try karein.")
                return
            
            await update.message.reply_text("🔍 Website data check kar raha hun... 🤖 AI se response le raha hun...")
            
            # Gemini se response lao
            ai_response = await self.get_ai_response(user_message, website_data)
            
            # Final response bhejo
            response_text = f"""
🙋 **Question:** {user_message}

🤖 **Answer:** 
{ai_response}

---
ℹ️ *Source: Rajasthan Tourism Official Website*
            """
            
            await update.message.reply_text(response_text)
            
        except Exception as e:
            logger.error(f"Handle message error: {e}")
            await update.message.reply_text("❌ Kuch technical problem aa gayi. Thodi der baad try karein.")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        welcome_text = """
🏰 **Namaste! BerortBot - Rajasthan Tourism Q&A Bot Me Swagat Hai** 🏰

Mujhe Rajasthan tourism ke bare mein kuch bhi pucho!
Main real-time official website se data lekar answer dunga.

**Examples puch sakte hain:**
• Rajasthan mein top tourist places
• Latest events kya chal rahe hain?
• Heritage hotels ke bare mein batao
• Travel guidelines kya hain?

Direct apna question likh do! 🤖
        """
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = """
🆘 **Help Guide:**

❓ **Kaise Kaam Karta Hai:**
1. Aap question likhte hain
2. Main Rajasthan tourism website se latest data leta hun
3. Gemini AI se process karta hun
4. Accurate answer milta hai

💡 **Sample Questions:**
• "Current festivals in Rajasthan"
• "Best time to visit Jaipur"
• "Rajasthan culture information"
• "Tourist packages available"

⚡ **Direct koi bhi question pucho!**
        """
        await update.message.reply_text(help_text)
    
    def setup_handlers(self, application):
        """All handlers setup kare"""
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

# Main function
def main():
    """Bot start kare"""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN missing!")
        print("❌ TELEGRAM_TOKEN environment variable set karein")
        return
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY missing!")
        print("❌ GEMINI_API_KEY environment variable set karein")
        return
    
    # Bot initialize kare
    bot = QABot()
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers setup kare
    bot.setup_handlers(application)
    
    # Start polling
    logger.info("BerortBot starting...")
    print("🚀 BerortBot Live Ho Gaya!")
    application.run_polling()

if __name__ == "__main__":
    main()
