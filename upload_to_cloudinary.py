import os
import django

from decouple import config
import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config( 
    cloud_name=config("CLOUD_NAME"), 
    api_key=config("API_KEY"), 
    api_secret=config("API_SECRET") 
)

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "babymuse.settings")
django.setup()

from shop.models import ProductImage  

def upload_old_media():
    for img in ProductImage.objects.all():
        if img.image and not str(img.image).startswith("http"):  # check if it's a local file
            local_path = img.image.path
            try:
                result = cloudinary.uploader.upload(local_path, folder="products/")
                img.image = result['secure_url']  # update image field with Cloudinary URL
                img.save()
            except Exception:
                pass 

if __name__ == "__main__":
    upload_old_media()
