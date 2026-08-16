# import smtplib
# from email.message import EmailMessage
# import mimetypes
# from pathlib import Path

# def send_alert_email(status, message_html_text, to_email, from_email, from_password,
#                      attachments=None, smtp_server='smtp.gmail.com', smtp_port=587):
#     # Templates by status
#     templates = {
#         'debug': f"""<html>
#         <body style="font-family: sans-serif; background-color: #eef5f9; padding: 20px;">
#             <div style="background-color: #d9edf7; padding: 20px; border-radius: 10px; color: #31708f;">
#                 <h2>DEBUG: Application started</h2>
#                 <p>{message_html_text}</p>
#             </div>
#         </body>
#         </html>""",
#         'warning': f"""<html>
#         <body style="font-family: sans-serif; background-color: #fff8e1; padding: 20px;">
#             <div style="background-color: #fcf8e3; padding: 20px; border-radius: 10px; color: #8a6d3b;">
#                 <h2>WARNING: Attention, possible unstable behavior</h2>
#                 <p>{message_html_text}</p>
#             </div>
#         </body>
#         </html>""",
#         'error': f"""<html>
#         <body style="font-family: sans-serif; background-color: #fbeaea; padding: 20px;">
#             <div style="background-color: #f2dede; padding: 20px; border-radius: 10px; color: #a94442;">
#                 <h2>ERROR: Critical incident!</h2>
#                 <p>{message_html_text}</p>
#             </div>
#         </body>
#         </html>"""
#     }

#     html_content = templates.get(status.lower(), templates['debug'])

#     msg = EmailMessage()
#     msg['Subject'] = f'ALERT [{status.upper()}]'
#     msg['From'] = from_email
#     msg['To'] = to_email
#     msg.set_content("Your email client does not support HTML.")
#     msg.add_alternative(html_content, subtype='html')

#     # Processing attachments
#     attachments = attachments or []
#     for path in attachments:
#         file_path = Path(path)
#         mime_type, _ = mimetypes.guess_type(file_path)
#         mime_type = mime_type or 'application/octet-stream'
#         maintype, subtype = mime_type.split('/', 1)
#         with open(file_path, 'rb') as f:
#             file_data = f.read()
#             msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_path.name)

#     # Sending
#     with smtplib.SMTP(smtp_server, smtp_port) as server:
#         server.starttls()
#         server.login(from_email, from_password)
#         server.send_message(msg)


# if __name__ == "__main__":
#     send_alert_email(
#         status='error',
#         message_html_text='A failure occurred in the image processing module. Intervention required.',
#         to_email='whitestoic@gmail.com',
#         from_email='your_email@gmail.com',
#         from_password='your_app_password',
#         attachments=[]
#     )