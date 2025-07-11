from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import razorpay
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hmac
import hashlib
import os
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

RAZORPAY_KEY_ID = "rzp_live_gvdyaC1uttFnEa"
RAZORPAY_KEY_SECRET = "8bPfhCaOnCf6t8TGr2IWjuWO"
EMAIL = "teja230704@gmail.com"
APP_PASSWORD = "hsim nlcm byyk mkuw"
MASTER_EMAIL = ["prabhavathigunda2@gmail.com","ayushmanbhava.help@gmail.com"]

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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

        redirect_url = f"/redirect_to_razorpay?order_id={order['id']}&amount={data.amount}&name={data.name}&phone={data.phone}&description={data.description}"
        return {"order_id": order['id'], "redirect_url": redirect_url, "status": "created"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/redirect_to_razorpay", response_class=HTMLResponse)
async def redirect_to_razorpay(order_id: str, amount: int, name: str, phone: str, description: str):
    return f"""
    <html>
    <head>
        <script src='https://checkout.razorpay.com/v1/checkout.js'></script>
    </head>
    <body>
        <script>
            var options = {{
                "key": "{RAZORPAY_KEY_ID}",
                "amount": "{amount}",
                "currency": "INR",
                "name": "Ayushman Bhava",
                "description": "{description}",
                "order_id": "{order_id}",
                "prefill": {{
                    "name": "{name}",
                    "contact": "{phone}"
                }},
                "theme": {{"color": "#F37254"}},
                "handler": function (response) {{
                    window.location.href = "/payment-success?razorpay_payment_id=" + response.razorpay_payment_id +
                                           "&razorpay_order_id=" + response.razorpay_order_id +
                                           "&razorpay_signature=" + response.razorpay_signature;
                }}
            }};
            var rzp = new Razorpay(options);
            rzp.open();
        </script>
    </body>
    </html>
    """

@app.post("/razorpay_webhook")
async def razorpay_webhook(request: Request):
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "your_webhook_secret")
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    try:
        expected_signature = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

        payload = await request.json()

        if payload.get("event") == "payment.captured":
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            name = payment_entity.get("notes", {}).get("name", "Unknown")
            phone = payment_entity.get("notes", {}).get("phone", "Unknown")
            description = payment_entity.get("notes", {}).get("description", "Yoga Class")
            amount = int(payment_entity.get("amount", 0)) // 100

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
            for i in MASTER_EMAIL:
                server.sendmail(EMAIL, i, msg.as_string())
            server.quit()

        return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")

@app.get("/payment-success", response_class=HTMLResponse)
async def payment_success(request: Request):
    try:
        params = dict(request.query_params)
        razorpay_payment_id = params.get("razorpay_payment_id")
        razorpay_order_id = params.get("razorpay_order_id")
        razorpay_signature = params.get("razorpay_signature")

        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(generated_signature, razorpay_signature):
            return HTMLResponse("<h2>❌ Signature verification failed. Payment is not trusted.</h2>", status_code=400)

        return f"""
        <html>
            <head><title>Payment Success</title></head>
            <body style='font-family:sans-serif; text-align:center; padding:50px;'>
                <h1>✅ Payment Successful!</h1>
                <p>Payment ID: <b>{razorpay_payment_id}</b></p>
                <p>Order ID: <b>{razorpay_order_id}</b></p>
                <p>Thank you for enrolling in the class.</p>
            </body>
        </html>
        """
    except Exception as e:
        return HTMLResponse(f"<h2>⚠ Error: {str(e)}</h2>", status_code=500)
