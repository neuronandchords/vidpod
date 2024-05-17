from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from datetime import date

Base = declarative_base()

class Podcast(Base):
    
    __tablename__ = 'podcasts'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, index=True)
    description = Column(String)
    link = Column(String)
    language = Column(String)
    explicit = Column(String)
    category = Column(String)
    image = Column(String)
    rss = Column(String)
    added_on = Column(Date, default= date.today())
    deleted_on = Column(Date, default= date.today())
    


class CreatePodcast(BaseModel):
    title : str
    description : str
    link : str
    language : str
    explicit : bool
    category : str
    image : str
    

class Episode(Base) : 
    
    __tablename__ = 'episodes'
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    podcast_id = Column(Integer, ForeignKey(Podcast.id))
    episode_no = Column(Integer)
    title = Column(String, index=True)
    description = Column(String)
    link = Column(String)
    duration = Column(String)
    audio_url = Column(String)
    pub_date = Column(Date)
    added_on = Column(Date, default= date.today())
    deleted_on = Column(Date, default= date.today())
    
class CreateEpisode(BaseModel):
    title : str
    description : str
    episode_no : int
    link : str
    podcast_id : int
    duration : str
    pub_date : date
    audio_url : str
    image : str