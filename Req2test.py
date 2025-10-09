from kivy.config import Config
Config.set('kivy', 'window_icon', 'logo.png')
import os
import re
import threading
import requests
from fpdf import FPDF
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, BooleanProperty
from kivy.clock import Clock
from datetime import datetime
from kivy.core.window import Window
from kivy.uix.image import Image

# The plyer import and file-loading functions have been removed as requested.

# --- Gemini API Configuration ---
API_KEY = "AIzaSyDpu3RIg4AiKnoWm0VczwXilxKPO64lcmM"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


# --- Markdown → Kivy Markup ---
def markdown_to_kivy(text):
    text = re.sub(r"\*\*(.*?)\*\*", r"[b]\1[/b]", text)
    text = re.sub(r"## (.*?)\n", r"[size=22][b]\1[/b][/size]\n", text)
    text = re.sub(r"# (.*?)\n", r"[size=26][b]\1[/b][/size]\n", text)
    text = re.sub(r"- ", r"• ", text)
    return text

# --- Remove markup for PDF ---
def clean_for_pdf(text):
    # Remove Kivy markup
    text = re.sub(r"\[/?[^\]]+\]", "", text) 
    # Remove Markdown bold/emphasis indicators
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    # Remove Kivy bullet conversion markers
    text = re.sub(r"•", "-", text)
    # Remove simple '#' headers (Fpdf will handle line breaks)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    # Reduce excessive newlines to ensure good spacing but preserve paragraphs
    text = re.sub(r"\n{3,}", "\n\n", text) 
    return text.strip()

# --- Gemini call via REST ---
def generate_with_gemini(requirement_text):
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"parts": [{"text": f"Generate structured test cases for:\n{requirement_text}"}]}
        ]
    }
    params = {"key": API_KEY}
    r = requests.post(GEMINI_URL, headers=headers, params=params, json=payload)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

# --- Kivy UI Class ---
class MyWidget(BoxLayout):
    displayed_text = StringProperty("Enter requirement to generate test cases or load a file.")
    is_generating = BooleanProperty(False)

    def generate_testcases(self, req_text):
        if self.is_generating:
            return
        req_text = req_text.strip()
        if not req_text:
            self.displayed_text = "[color=ff3333]Please enter a requirement first![/color]"
            return

        self.is_generating = True
        self.displayed_text = "[i]Generating test cases... please wait[/i]"
        threading.Thread(target=self._generate_in_background, args=(req_text,), daemon=True).start()

    def _generate_in_background(self, req_text):
        try:
            result_text = generate_with_gemini(req_text)
            formatted = markdown_to_kivy(result_text)
            Clock.schedule_once(lambda dt: self._update_ui_after_generation(formatted, None), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self._update_ui_after_generation(None, err), 0)

    def _update_ui_after_generation(self, formatted_text, error_msg):
        self.is_generating = False
        if error_msg:
            self.displayed_text = f"[color=ff0000]Error: {error_msg}[/color]"
        elif formatted_text:
            self.displayed_text = formatted_text
        else:
            self.displayed_text = "[color=ff0000]Error: Generation failed with no output.[/color]"

    # --- PDF Export ---
    def download_pdf(self):
        from datetime import datetime
        cleaned_text = clean_for_pdf(self.displayed_text)

        if not cleaned_text.strip() or "[i]Generating test cases..." in cleaned_text:
            self.displayed_text = "[color=ff3333]No test cases to save! Generate them first.[/color]"
            return

        try:
            app_dir = App.get_running_app().user_data_dir
            filename = os.path.join(app_dir, f"TestCases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Helvetica", size=10)
            page_width = pdf.w - 2 * pdf.l_margin

            # Pass the entire cleaned text to multi_cell for proper wrapping and spacing.
            pdf.multi_cell(page_width, 5, txt=cleaned_text)

            pdf.output(filename)
            self.displayed_text = f"[color=00ff00]PDF saved to {filename}[/color]"

        except Exception as e:
            self.displayed_text = f"[color=ff0000]Error saving PDF: {e}[/color]"


# --- KV Layout ---
KV_CODE = """
<MyWidget>:
    orientation: "vertical"
    padding: 15
    spacing: 10

    ScrollView:
        size_hint_y: 0.7
        do_scroll_x: False
        do_scroll_y: True
        Label:
            text: root.displayed_text
            markup: True
            font_size: "16sp"
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]

    TextInput:
        id: req_input
        hint_text: "Enter requirement here..."
        multiline: True
        size_hint_y: 0.2

    BoxLayout:
        size_hint_y: 0.1
        spacing: 10

        Button:
            text: "Generate"
            on_release: root.generate_testcases(req_input.text)
            disabled: root.is_generating
            size_hint_x: 0.5 # Balance width after removing Load File button

        Button:
            text: "Download PDF"
            on_release: root.download_pdf()
            disabled: root.is_generating
            size_hint_x: 0.5 # Balance width after removing Load File button

"""

Builder.load_string(KV_CODE)

class TestCaseApp(App):
    def build(self):
        self.title = "Req2Test"
        Window.icon = "logo.png"
        return MyWidget()

if __name__ == "__main__":
    TestCaseApp().run()
