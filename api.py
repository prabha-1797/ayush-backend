from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import razorpay
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hmac
import hashlib
import os

app = FastAPI()

# Razorpay Keys (store securely in env vars in real deployment)
RAZORPAY_KEY_ID = "rzp_test_eT9lCdOnYfweo9"
RAZORPAY_KEY_SECRET = "1BIW3EN9r4igx1VvKirXnABf"

# Email credentials
EMAIL = "teja230704@gmail.com"
APP_PASSWORD = "hsim nlcm byyk mkuw"
MASTER_EMAIL = "prabhavathigunda2@gmail.com"

# Razorpay Client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Order initiation endpoint
class OrderRequest(BaseModel):
    amount: int
    name: str
    phone: str
    description: str

@app.get("/")
def home():
    return "this endpoint doesn't support get requests"
@app.post("/create_order")
async def create_order(data: OrderRequest):
    try:
        order = razorpay_client.order.create({
            "amount": data.amount,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "name": data.name,
                "phone": data.phone,
                "description": data.description
            }
        })
        return {"order_id": order['id'], "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Razorpay webhook verification endpoint
@app.post("/razorpay_webhook")
async def razorpay_webhook(request: Request):
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "your_webhook_secret")
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    try:
        # Verify signature
        expected_signature = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

        payload = await request.json()

        if payload.get("event") == "payment.captured":
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            name = payment_entity.get("notes", {}).get("name", "Unknown")
            phone = payment_entity.get("notes", {}).get("phone", "Unknown")
            description = payment_entity.get("notes", {}).get("description", "Yoga Class")
            amount = int(payment_entity.get("amount", 0)) // 100

            # Send email to master
            msg = MIMEMultipart()
            msg['From'] = EMAIL
            msg['To'] = MASTER_EMAIL
            msg['Subject'] = "New Course Enrollment Notification"

            body = f"""
            A new user has enrolled.
            Name: {name}
            Phone: {phone}
            Class: {description}
            Amount: ₹{amount}
            Payment ID: {payment_entity.get("id")}
            """
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL, APP_PASSWORD)
            server.sendmail(EMAIL, MASTER_EMAIL, msg.as_string())
            server.quit()

        return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")
