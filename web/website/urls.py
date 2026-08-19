"""
This reroutes from an URL to a python view-function/class.

The main web/urls.py includes these routes for all urls (the root of the url)
so it can reroute to all website pages.

"""

from django.urls import path

from evennia.web.website.urls import urlpatterns as evennia_website_urlpatterns

from web.website.views.guides import home_view, how_to_play_view, new_players_view, armory_view, races_view, map_view

# add patterns here
urlpatterns = [
    path("", home_view, name="home"),
    path("how-to-play", how_to_play_view, name="how-to-play"),
    path("new-players", new_players_view, name="new-players"),
    path("armory", armory_view, name="armory"),
    path("races", races_view, name="races"),
    path("map", map_view, name="map"),
]

# read by Django
urlpatterns = urlpatterns + evennia_website_urlpatterns
