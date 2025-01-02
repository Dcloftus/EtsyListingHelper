from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.platypus import Image as platImage
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
import dropbox
from PIL import Image
from openai import OpenAI
import base64
import os
import sys
import random

#======================================================================================
#= Global Variables
#======================================================================================
# Define the source folder and output folder
source_folder = '../Source Files'
output_folder = '../Exported Files'
# sections_path = '../Generator Data/Sections.txt'

# Ensure the output folder exists
os.makedirs(output_folder, exist_ok=True)

# Define the target sizes
variants = {
    "2_3 Ratio" : {
        "20inx30in": (6000, 9000),
        "16inx24in": (4800, 7200),
        "12inx18in": (3600, 5400),
        "8inx12in": (2400, 3600),
        "6inx9in": (1800, 2700),
        "4inx6in": (1200, 1800),
    },
    "4_5 Ratio" : {
        "16inx20in": (4800, 6000),
        "12inx15in": (3600, 4500),
        "8inx10in": (2400, 3000),
        "4inx5in": (1200, 1500),
    },
    "3_4 Ratio" : {
        "18inx24in": (5400, 7200),
        "12inx16in": (3600, 4800),
        "9inx12in": (2700, 3600),
        "6inx8in": (1800, 2400),
    }

    # # TEST Smaller 3:4 Ratio Sizes
    # "3_4 Ratio" : {
    #     "18inx24in": (540, 720),
    #     "12inx16in": (360, 480),
    #     "9inx12in": (270, 360),
    #     "6inx8in": (180, 240),
    # }
}

# Drop Box Token
ACCESS_TOKEN = 'AccessTokenHere'


# Chat GPT variables
IMAGE_PATH = "Source Files/Art2x3@300DPITEST.png"
MODEL="gpt-4o-mini"

# Set up your OpenAI API key
client = OpenAI(
    # This is the default and can be omitted
    api_key='APIKeyHere',
)

#======================================================================================
#= Funcitons
#======================================================================================
def overlay_images(background_path, foreground_path, output_folder, overlay_target_width, destination):
    """
    Overlays a foreground image on top of a background image.
    
    Parameters:
    - background_path (str): Path to the background image file.
    - foreground_path (str): Path to the foreground image file.
    - output_folder (str): Folder where the resulting image will be saved.
    - overlay_target_width (int): Desired width for the foreground image while maintaining its aspect ratio.
    """

    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Open the background and foreground images
    with Image.open(background_path) as background:
        with Image.open(foreground_path) as foreground:
            # Resize the foreground image to 851 pixels wide, maintaining aspect ratio
            aspect_ratio = foreground.height / foreground.width
            new_height = int(overlay_target_width * aspect_ratio)
            foreground = foreground.resize((overlay_target_width, new_height), Image.LANCZOS)
            
            # Calculate the position to center the foreground on the background
            background_width, background_height = background.size
            foreground_width, foreground_height = foreground.size
            
            # Calculate top-left coordinates to center the foreground
            left = (background_width - foreground_width) // 2
            top = (background_height - foreground_height) // 2
            
            # Overlay the foreground on the background, centered
            background.paste(foreground, (left, top), foreground)

            # Define the output path
            output_image_path = os.path.join(output_folder, destination + '_overlayed_image.png')
            
            # Save the resulting image
            background.save(output_image_path)

    print(f"{destination} cover image saved at {output_image_path}")

def crop_and_resize(image_file, source_image_path, export_folder, base_name, ext):
    #Creating a folder for just the images
    export_folder = os.path.join(export_folder, base_name)
    # Ensure the output folder exists
    os.makedirs(export_folder, exist_ok=True)

    # Cropping and Resizing
    try:
        print(f"Starting to Process {image_file}")
        # Open the source image
        with Image.open(source_image_path) as img:
            # Iterate over the ratios
            for ratio, sizes in variants.items():
                ratio_export_folder = os.path.join(export_folder, ratio)
                # Ensure the output folder exists
                os.makedirs(ratio_export_folder, exist_ok=True)
                # Iterate over the sizes in ratio
                for label, size in sizes.items():
                    # Calculate the aspect ratio of the target size
                    target_ratio = size[0] / size[1]
                    img_ratio = img.width / img.height

                    if target_ratio > img_ratio:
                        # Target is wider, crop height to match aspect ratio
                        new_height = int(img.width / target_ratio)
                        top = (img.height - new_height) // 2
                        cropped_img = img.crop((0, top, img.width, top + new_height))
                    else:
                        # Target is taller, crop width to match aspect ratio
                        new_width = int(img.height * target_ratio)
                        left = (img.width - new_width) // 2
                        cropped_img = img.crop((left, 0, left + new_width, img.height))

                    # Resize the cropped image to the target size
                    resized_img = cropped_img.resize(size, Image.LANCZOS)

                    # Define the output path using the original filename and size label in its own ratio_export_folder
                    output_path = os.path.join(ratio_export_folder, f'{base_name}_{label}{ext}')

                    # Save the final image
                    resized_img.save(output_path)
                    print(f"Saved {base_name} - {label}")

        print(f"Processed {image_file}")

    except Exception as e:
        print(f"An error occurred with {image_file}: {e}")

def upload_file_to_dropbox(local_file_path, dropbox_destination_path, dbx):
    """Uploads a single file to Dropbox."""
    with open(local_file_path, 'rb') as f:
        dbx.files_upload(f.read(), dropbox_destination_path)

def upload_folder_to_dropbox(local_folder_path, dropbox_folder_path, dbx):
    """Uploads all files in a local folder to Dropbox."""
    for root, dirs, files in os.walk(local_folder_path):
        for filename in files:
            #Skip .DS_Store files
            if filename == '.DS_Store':
                continue

            #Skip _overlayed_image.png files
            if filename == '*_overlayed_image.png':
                continue

            # Construct full local file path
            local_file_path = os.path.join(root, filename)
            # Construct the Dropbox destination path
            relative_path = os.path.relpath(local_file_path, local_folder_path)
            dropbox_destination_path = os.path.join(dropbox_folder_path, relative_path)
            # Ensure Dropbox destination path uses forward slashes
            dropbox_destination_path = dropbox_destination_path.replace(os.sep, '/')
            print(f"Uploading {local_file_path} to {dropbox_destination_path}...")
            upload_file_to_dropbox(local_file_path, dropbox_destination_path, dbx)

def create_shared_link(dropbox_folder_path, dbx):
    """Creates a shared link for the uploaded folder."""
    try:
        # Create shared link
        shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_folder_path)
        return shared_link.url
    except dropbox.exceptions.ApiError as e:
        print(f"Error creating shared link: {e}")
        return None

def get_shared_link(dropbox_folder_path, dbx):
    """Retrieves an existing shared link for a folder or creates a new one if none exists."""
    try:
        # Check for existing shared links
        shared_links = dbx.sharing_list_shared_links(path=dropbox_folder_path)
        
        # If a shared link already exists, return the first one
        if shared_links.links:
            return shared_links.links[0].url
        else:
            # If no shared link exists, create a new one
            shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_folder_path)
            return shared_link.url
    except dropbox.exceptions.ApiError as e:
        print(f"Error getting or creating shared link: {e}")
        return None

def add_background_color(canvas, doc):
    # Get the width and height of the page
    width, height = letter
    # Set the background color to a light blue (or any color)
    canvas.setFillColor("#F3EDE4")
    # Draw a rectangle that covers the entire page
    canvas.rect(0, 0, width, height, fill=1)

def create_pdf(file_name, href_Link):
    # Create a PDF document
    pdf = SimpleDocTemplate(file_name, pagesize=letter)

    # Get the default style for paragraphs
    styles = getSampleStyleSheet()

    # Create a custom style for centered text
    centered_style = ParagraphStyle(
        name="Centered",
        parent=styles["Normal"],
        alignment=TA_CENTER,  # Aligns the text to the center
        fontSize=16,
        textColor="#454545",
        leading=20
    )

    bold = ParagraphStyle(
        name="Bold",
        parent=styles["Normal"],
        alignment=TA_CENTER,  # Aligns the text to the center
        fontName="Helvetica-Bold",  # Bold weight
        fontSize=16,
        textColor="#454545",
        leading=20
    )

    link = ParagraphStyle(
        name="Bold",
        parent=styles["Normal"],
        alignment=TA_CENTER,  # Aligns the text to the center
        fontName="Helvetica-Bold",  # Bold weight
        fontSize=26,
        textColor="#0057FF",
    )

    # Load the image and set its size (optional)
    img = platImage("../Generator Data/Profile Picture PDF.png")
    img.drawWidth = 250    # Set to original width
    img.hAlign = 'CENTER'  # Align the image to the center

    # Define your text (this is a long string that will wrap)
    first = """
    Thank you so much for purchasing one of my digital prints from 
    Art to Aviation! Your support means the world to me as I work towards 
    turning my dream of becoming a pilot into reality.
    """

    second = """
    I hope the art brings as much joy to you as it did for me while creating 
    it. If you have any questions or would like to share how you're displaying it, 
    I’d love to hear from you!
    """

    third = """
    Thanks again for being a part of this journey. Your purchase is one step closer 
    to me soaring the skies!
    """

    fourth = """
    Click below to access the full resolution files in Drop Dox, from there you 
    can download any and all sizes at their highest quality!
    """

    download = f"""
    <a href="{href_Link}" color="blue">Download Files</a>
    """

    # Create a paragraph with the text and the custom centered style
    first_paragraph = Paragraph(first, centered_style)
    second_paragraph = Paragraph(second, centered_style)
    third_paragraph = Paragraph(third, centered_style)
    fourth_paragraph = Paragraph(fourth, bold)
    download_link = Paragraph(download, link)

    # Add the paragraph to a list of flowables
    elements = []

    elements.append(img)
    # Add some space after the Image
    elements.append(Spacer(1, 75))
    elements.append(first_paragraph)
    # Add some space after the paragraph
    elements.append(Spacer(1, 24))
    elements.append(second_paragraph)
    # Add some space after the paragraph
    elements.append(Spacer(1, 24))
    elements.append(third_paragraph)
    # Add some space after the paragraph
    elements.append(Spacer(1, 74))
    elements.append(fourth_paragraph)
    # Add some space after the paragraph
    elements.append(Spacer(1, 24))
    elements.append(download_link)

    # Build the PDF with the flowables (text in this case)
    pdf.build(elements, onFirstPage=add_background_color, onLaterPages=add_background_color)

    
#======================================================================================
#= Main Funciton on each source image
#======================================================================================
def main(crop, cover, drop, pdf, gpt):
    # Print the arguments to show they were received
    print(f"Crop and Resize on?     : {crop}")
    print(f"Create Cover Images on? : {cover}")
    print(f"Push to DropBox on?     : {drop}")
    print(f"Create PDF on?          : {pdf}")
    print(f"Chat GPT call on?       : {gpt}")

    # Get a list of all image files in the source folder
    image_files = [f for f in os.listdir(source_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]

    for image_file in image_files:
        source_image_path = os.path.join(source_folder, image_file)
        base_name, ext = os.path.splitext(image_file)

        # Create specific output folders in "Exported Files" folder
        export_folder = output_folder + "/" + base_name
        os.makedirs(export_folder, exist_ok=True)

        #Cropping and resizing
        if(crop == 'true'):
            crop_and_resize(image_file, source_image_path, export_folder, base_name, ext)
        else:
            print("Cropping and Resizing is turned off!")

        #Etsy Cover images
        if(cover == 'true'):
            #overlay_number = 4
            # Create a random number between 1 and 4 to pick the overlay image.
            overlay_number = random.randint(1, 4)

            etsy_cover_background = '../Generator Data/EtsyCoverOverlay' + str(overlay_number) + '.png'
            instagram_cover_background = '../Generator Data/InstagramCoverOverlay' + str(overlay_number) + '.png'


            overlay_images(etsy_cover_background, source_image_path, export_folder, 851, "Etsy")
            #Instagram Cover images
            overlay_images(instagram_cover_background, source_image_path, export_folder, 505, "Instagram")
        else:
            print("Cover image creation is turned off!")

        #Push Images to drop box
        if(drop == 'true'):
            # Connect to Dropbox
            dbx = dropbox.Dropbox(ACCESS_TOKEN)

            # Define the local folder to upload and the Dropbox folder destination
            local_folder_path = export_folder + '/' + base_name  # Replace with your local folder path
            dropbox_folder_path = '/' + base_name   # Replace with desired Dropbox folder path

            # Upload the folder
            upload_folder_to_dropbox(local_folder_path, dropbox_folder_path, dbx)

            # Get shared link for the folder
            shared_link = get_shared_link(dropbox_folder_path, dbx)
            print(shared_link)

        #Create PDF Download Guide
        if(pdf == 'true'):
            pdf_export_folder = export_folder + "/DownloadGuide.pdf"
            create_pdf(pdf_export_folder, shared_link)
            print("Created PDF at: " + pdf_export_folder)
        else:
            print("Creating PDF is turned off!")

        # Converting image into base64 so chat gpt can understand it
        if(gpt == 'true'):
            # Get the last item in sizes dict
            last_ratio_key, last_ratio_value = list(variants.items())[-1]
            # print(f"Last Key:  {last_ratio_key}")
            # print(f"Last Value:  {last_ratio_value}")
            last_size_key, last_size_value = list(last_ratio_value.items())[-1]
            # print(f"Last Key:  {last_size_key}")
            # print(f"Last Value:  {last_size_value}")

            with open(export_folder + "/" + f'{base_name}' + "/" + f'{last_ratio_key}' + "/" + f'{base_name}_{last_size_key}{ext}', "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            # Using Chat GPT 4o Mini to write descriptions off of source images
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that describes digital artwork for a listing optimising for searchability. Use a friendly tone and make it as natural as possible."},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Please create an etsy title and description of the image. Refrane from using the word etsy in the description. Please add a section for this listing to live in. Please add 13 related tags optimized to help with search visability in a comma seperated list, each tag can not be loger than 20 characters. Please add an instagram description. Please add instagram hashtag optimized for search visability."},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"}
                        }
                    ]}
                ],
                temperature=0.0,
            )
            #print(response.choices[0].message.content)
            # Open the file in write mode ('w')
            description_path = export_folder + "/" + base_name + ".txt"
            with open(description_path, 'w') as file:
                # Write the text to the file
                file.write(response.choices[0].message.content)

            print(f"Text has been written to {description_path}")
        else:
            print("Calling Chat GPT is turned off!")

    print("Complete")

if __name__ == "__main__":
    # Ensure there are exactly 4 arguments (including the script name)
    if len(sys.argv) != 6:
        print("Usage: python3 test.py <crop> <cover> <drop> <pdf> <gpt>")
        sys.exit(1)
    
    # Extract arguments
    _, crop, cover, drop, pdf, gpt = sys.argv
    
    # Call the main function with the provided arguments
    main(crop, cover, drop, pdf, gpt)
