from rest_framework.response import Response
from rest_framework import status
from content.serializers.contact import ContactSerializer
from rest_framework.decorators import api_view
from content.utils import send_email_notification

@api_view(['POST'])
def new_contact(request):
    """
    API view to create a new Contact message.
    """
    serializer = ContactSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        contact = serializer.save()
        
        # Prepare data for email notification
        email = contact.email
        phone = contact.phone_number or 'No proporcionado'
        subject = contact.subject
        message = contact.message
        budget = contact.budget or 'No especificado'
        
        # Create email subject and body
        email_subject = f"Nuevo mensaje de contacto: {subject}"
        email_body = f"""
Nuevo mensaje de contacto recibido:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email: {email}
📱 Teléfono: {phone}
💰 Presupuesto: {budget}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 Asunto: {subject}

💬 Mensaje:
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Este mensaje fue enviado desde el formulario de contacto de projectapp.co
        """
        
        # Send email notification
        send_email_notification(email_subject, email_body)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
