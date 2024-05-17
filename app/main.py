import os
import feedparser
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from xml.etree import ElementTree as ET
from models.models import *
from sqlalchemy.orm import Session
from models.db import *
from datetime import datetime
from aws.s3 import *
from aws.polly import *
from openai import OpenAI
from bs4 import BeautifulSoup
import time


app = FastAPI()

client = OpenAI(
    # This is the default and can be omitted
    api_key="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",
)

class RSSUrl(BaseModel):
    url : str


def generate_episode_id(entry):
    # Generate a unique identifier for each episode (e.g., using entry ID or title)
    return entry.id


@app.get("/")
def root():
    return {"message": "Hello World"}
    
    
def fetch_podcast_data(rss_feed_url):
    feed = feedparser.parse(rss_feed_url)
    if not feed.entries:
        return None
    
    podcast_data = {}
    podcast_data["title"] = feed.feed.title
    podcast_data["description"] = feed.feed.description
    podcast_data["episodes"] = []
    podcast_data["image"] = feed.feed.image.url if feed.feed.image.url else ""
    podcast_data["website"] = "https://vidpod.ai"
    
    for entry in feed.entries:
        episode = {
            "title": entry.title,
            "description": entry.description,
            "pub_date": entry.published,
            "audio_url": entry.enclosures[0].href,  # Assuming the audio file URL is in the enclosures
            "audio_length": entry.enclosures[0].length  # Length of audio file in bytes
        }
        podcast_data["episodes"].append(episode)
    
    return podcast_data

def generate_xml(podcast_data, db):
    
    namespaces = {
        "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        "atom": "http://www.w3.org/2005/Atom"
    }
    
    root = ET.Element("rss", attrib={"version": "2.0"})
    
    for ns, url in namespaces.items():
        ET.register_namespace(ns, url)

    # Create channel element
    channel = ET.SubElement(root, "channel")

    podcast = Podcast(title=podcast_data["title"], description=podcast_data["description"], link=podcast_data["website"],
                      language=podcast_data.get("language", "en"), explicit=podcast_data.get("explicit", "no"),
                      category=podcast_data.get("category", "Podcast")
                      )
    db.add(podcast)
    db.commit()
    podcast.link = f"https://vidpod.ai/podcast/{podcast.id}"
    vidpod_img_url = upload_audio_to_s3(podcast_data["image"], 0, podcast.id, "image")
    podcast.image = vidpod_img_url

    # Populate channel metadata
    ET.SubElement(channel, "title").text = podcast_data["title"]
    ET.SubElement(channel, "description").text = podcast_data["description"]
    ET.SubElement(channel, "link").text = podcast_data.get("website", "")  # Add website link if available
    ET.SubElement(channel, "language").text = podcast_data.get("language", "en")  # Add language tag
    
    itunes_namespace = "{" + namespaces["itunes"] + "}"
    
    # ET.SubElement(
    #     channel,
    #     "atom:link",
    #     href=f"https://vidpod.ai/podcast/{podcast.id}/rss",
    #     rel="self",
    #     type="application/rss+xml",
    # )
    
    ET.SubElement(channel, "{%s}link" % namespaces["atom"], rel="self", href=f"https://vidpod.ai/podcast/{podcast.id}/rss")

    # Add image tag to channel
    image_elem = ET.SubElement(channel, "image")
    ET.SubElement(image_elem, "url").text = vidpod_img_url
    ET.SubElement(image_elem, "title").text = podcast_data['title']
    ET.SubElement(image_elem, "link").text = podcast_data.get("website")

    # Add iTunes-specific tags
    # ET.SubElement(channel, "itunes:image", href=vidpod_img_url)
    # ET.SubElement(channel, "itunes:category", text=podcast_data.get("category", "Podcast"))
    # ET.SubElement(channel, "itunes:explicit").text = podcast_data.get("explicit", "no")
    
    ET.SubElement(channel, itunes_namespace + "image", href=vidpod_img_url)
    ET.SubElement(channel, itunes_namespace + "category", text=podcast_data.get("category", "Podcast"))
    ET.SubElement(channel, itunes_namespace + "explicit").text = podcast_data.get("explicit", "no")
    
    
    ET.SubElement(
        channel, "generator"
    ).text = (
        "Vidpod"
    )

    # Adds explicit tag
    itunes_explicit = ET.SubElement(channel, "itunes:explicit")
    itunes_explicit.text = podcast_data.get("explicit", "no")

    # # Add itunes:owner and itunes:email tags
    # itunes_owner = ET.SubElement(channel, "itunes:owner")
    # ET.SubElement(itunes_owner, "itunes:email").text = podcast_data[]

    # # Add itunes:author tag
    # itunes_author = ET.SubElement(channel, "itunes:author")
    # itunes_author.text = metadata["itunes_author"]

    # Duplicate description to itunes summary
    # itunes_summary = ET.SubElement(channel, "itunes:summary")
    # itunes_summary.text = podcast_data["description"]
    
    itunes_summary = ET.SubElement(channel, itunes_namespace + "summary")
    itunes_summary.text = podcast_data["description"]
    
    # ET.SubElement(channel, "itunes:summary").text = podcast_data["description"]

    # Add itunes:category tag
    # ET.SubElement(channel, "itunes:category", text="Podcast")
    ET.SubElement(channel, itunes_namespace + "category").text = "Podcast"

    # itunes_image = ET.SubElement(channel, "itunes:image")
    # itunes_image.set("href", podcast_data["image"])
    

    # Add episodes
    for i, episode in enumerate(podcast_data["episodes"]):
        try:
            pub_date = datetime.strptime(episode["pub_date"], '%a, %d %b %Y %H:%M:%S %z').date()
        except:
            pub_date = datetime.strptime(episode["pub_date"], '%a, %d %b %Y %H:%M:%S %Z').date()
        vidpod_audio_url = upload_audio_to_s3(episode["audio_url"], i, podcast.id, "audio")

        episode_obj = Episode(title=episode["title"], description=episode["description"], link=episode.get("link", ""),
                              pub_date=pub_date, episode_no=i, podcast_id=podcast.id, duration=episode["audio_length"],
                              audio_url=vidpod_audio_url)
        db.add(episode_obj)
        db.commit()

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = episode["title"]
        ET.SubElement(item, "description").text = episode["description"]
        ET.SubElement(item, "pubDate").text = episode["pub_date"]
        ET.SubElement(item, "link").text = episode.get("link", "")  # Add link if available
        ET.SubElement(item, "enclosure", attrib={
            "url": vidpod_audio_url,
            "length": str(episode["audio_length"]),
            "type": "audio/mpeg"
        })
        
        print(f"Episode{i} uploaded!")
        
    podcast.rss = ET.tostring(root, encoding="utf-8")

    return ET.tostring(root, encoding="utf-8"), podcast

@app.post("/import/rss")
def podcast_importer(rss_feed_url : RSSUrl, db: Session = Depends(get_db)):
    # rss_url = upload_file(local_file_path="podcast_final.xml")
    # return {"rss" : rss_url }
    podcast_data = fetch_podcast_data(rss_feed_url.url)
    if podcast_data:
        xml_content, podcast = generate_xml(podcast_data, db)
        
        # Write XML content to a file or upload to your server
        with open(f"podcast_{podcast.id}.xml", "wb") as f:
            f.write(xml_content)
            rss_url = upload_file(local_file_path=f"podcast_{podcast.id}.xml")
        
        print("XML file generated successfully.")
        return {"rss" : rss_url }
    else:
        print("Failed to fetch podcast data from the RSS feed URL.")
        
        
        
@app.post("/generate/rss")
def fake_podcast_generator():
    return True
    
@app.post("/generate_fake_rss")   
async def generate_fake_rss(prompt: str, db: Session = Depends(get_db)):
    try:
        # Define the user role
        user_role = "You are an expert RSS feed creator. The RSS feeds you have created have been worldwide famous and accurate, always following best practices, and always accepted by iTunes, Apple, and Spotify. It contains all the proper tags and is a rich RSS that has all the information related to the podcast"

        # Prompt with the specified user role
        full_prompt = f"Given a prompt generate rss feed for the podcast about the prompt Your prompt is - {prompt}. Fetch images from unsplash using the description of the episode and podcast title and put that url in rss feed, it should have atleast 3 episodes, and description of each episode should be atleast 200 words long. NO PRE OR POST TEXT JUST THE SCRIPT"

        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {
                "role": "system",
                "content": "You are an expert RSS feed creator. The RSS feeds you have created have been worldwide famous and accurate, always accepted by iTunes, Apple, and Spotify. It contains all the proper tags and is a rich RSS that has all the information related to the podcast"
                },
                {
                "role": "user",
                "content": "Given a prompt generate rss feed for the podcast about the prompt Your prompt is - \"How can music change the world\" Fetch images from unsplash using the description of the episode and podcast title and put that url in rss feed, it should have atleast 3 episodes, and description of each episode should be atleast 200 words long. NO PRE OR POST TEXT JUST THE SCRIPT"
                },
                {
                "role": "assistant",
                "content": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\" xmlns:itunes=\"http://www.itunes.com/dtds/podcast-1.0.dtd\" xmlns:content=\"http://purl.org/rss/1.0/modules/content/\">\n<channel>\n  <title>How Music Can Change the World</title>\n  <link>https://www.example.com/podcast</link>\n  <language>en-us</language>\n  <itunes:subtitle>Exploring the impact of music on society and global change</itunes:subtitle>\n  <itunes:image href=\"[UNPLASH_IMAGE_URL]\" />\n  <description>Join us as we delve into the transformative power of music and discuss how it can create positive change in the world. Each episode features interviews with musicians, activists, and scholars who share their insights on the topic. Discover inspiring stories of artists who have utilized music to break social barriers, raise awareness, and inspire social change. If you believe in the power of music to shape our world, this podcast is for you.</description>\n  <itunes:author>John Doe</itunes:author>\n  <itunes:category text=\"Music\" />\n  <itunes:explicit>no</itunes:explicit>\n  \n  <!-- Episode 1 -->\n  <item>\n    <title>The Role of Music in Social Movements</title>\n    <itunes:author>John Doe</itunes:author>\n    <pubDate>Mon, 01 Jan 2023 00:00:00 GMT</pubDate>\n    <itunes:image href=\"[UNPLASH_IMAGE_URL]\" />\n    <enclosure url=\"https://www.example.com/episodes/episode1.mp3\" length=\"13456789\" type=\"audio/mpeg\" />\n    <itunes:duration>57:32</itunes:duration>\n    <itunes:explicit>no</itunes:explicit>\n    <description>On this episode, we explore the historical significance of music in social movements. From the Civil Rights Movement to modern-day protests, music has played a crucial role in inspiring change, fostering unity, and giving a voice to the marginalized. Our guest, renowned musicologist Jane Smith, shares her research on the subject while shedding light on iconic songs that have become anthems for justice and equality.</description>\n  </item>\n  \n  <!-- Episode 2 -->\n  <item>\n    <title>Music as a Catalyst for Global Awareness</title>\n    <itunes:author>John Doe</itunes:author>\n    <pubDate>Mon, 08 Jan 2023 00:00:00 GMT</pubDate>\n    <itunes:image href=\"[UNPLASH_IMAGE_URL]\" />\n    <enclosure url=\"https://www.example.com/episodes/episode2.mp3\" length=\"12345678\" type=\"audio/mpeg\" />\n    <itunes:duration>41:20</itunes:duration>\n    <itunes:explicit>no</itunes:explicit>\n    <description>In this episode, we dive into the power of music to raise global awareness on pressing issues. Our guest, acclaimed artist and activist Sarah Johnson, shares her personal journey in using music as a tool to shed light on environmental concerns, social injustice, and humanitarian crises. Through heartful storytelling and captivating music, Sarah demonstrates how artists can drive change and foster empathy on a global scale.</description>\n  </item>\n  \n  <!-- Episode 3 -->\n  <item>\n    <title>Building Communities Through Music Education</title>\n    <itunes:author>John Doe</itunes:author>\n    <pubDate>Mon, 15 Jan 2023 00:00:00 GMT</pubDate>\n    <itunes:image href=\"[UNPLASH_IMAGE_URL]\" />\n    <enclosure url=\"https://www.example.com/episodes/episode3.mp3\" length=\"14567890\" type=\"audio/mpeg\" />\n    <itunes:duration>1:10:15</itunes:duration>\n    <itunes:explicit>no</itunes:explicit>\n    <description>On our final episode, we explore the role of music education in building communities and creating lasting social change. Our guest, renowned music educator Mark Thompson, shares his insights on how music programs can empower individuals, bridge cultural divides, and promote inclusivity. Join us as we discuss the transformative power of music education and the positive impact it can have on our society.</description>\n  </item>\n  \n</channel>\n</rss>"
                },
                {
                "role": "user",
                "content": f"Given a prompt generate rss feed for the podcast about the prompt Your prompt is - {prompt} Fetch images from unsplash using the description of the episode and podcast title and put that url in rss feed, it should have atleast 3 episodes, and description of each episode should be atleast 200 words long. NO PRE OR POST TEXT JUST THE SCRIPT"
                },
            ],
            temperature=1,
            max_tokens=12203,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )

        # Extract and return the generated text
        # print(response.choices[0].message.content)
        data = populate_fake_podcast(response.choices[0].message.content)
        
        
        if data:
            xml_content, podcast = generate_xml(data, db)
            with open(f"podcast_{podcast.id}.xml", "wb") as f:
                f.write(xml_content)
                rss_url = upload_file(local_file_path=f"podcast_{podcast.id}.xml")
            
            print("XML file generated successfully.")
        else:
            print("Failed to fetch podcast data from the RSS feed URL.")
            
        return {"rss": rss_url}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    
def populate_fake_podcast(rss_feed):
    
    feed = feedparser.parse(rss_feed)
    if not feed.entries:
        return None
    
    podcast_data = {}
    podcast_data["title"] = feed.feed.title
    podcast_data["description"] = feed.feed.description
    podcast_data["episodes"] = []
    podcast_data["image"] = "https://images.unsplash.com/photo-1715586041798-9583f0642747?q=80&w=2787&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
    podcast_data["website"] = "https://vidpod.ai"
    
    for i, entry in enumerate(feed.entries):
        audio_url = text_to_speech(i, entry.description)
        # print(audio_url)
        episode = {
            "title": entry.title,
            "description": entry.description,
            "pub_date": entry.published,
            "audio_url": audio_url,  # Assuming the audio file URL is in the enclosures
            "audio_length": entry.enclosures[0].length  # Length of audio file in bytes
        }
        podcast_data["episodes"].append(episode)
    
    # print(podcast_data)
    return podcast_data
        
        
@app.post("/podcast/create")
def create_podcast(podcast: CreatePodcast, db: Session = Depends(get_db)):
    db_item = Podcast(**podcast.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.get("/podcast/{podcast_id}")
def read_podcast(podcast_id: int, db: Session = Depends(get_db)):
    db_item = db.query(Podcast).filter(Podcast.id == podcast_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return db_item


@app.get("/episodes/{podcast_id}")
def read_podcast(podcast_id: int, db: Session = Depends(get_db)):
    db_item = db.query(Episode).filter(Episode.podcast_id == podcast_id).all()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return db_item
    
    