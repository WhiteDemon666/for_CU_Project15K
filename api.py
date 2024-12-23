import requests
from datetime import datetime


class AccuWeather:
    def __init__(self, api_key, url='http://dataservice.accuweather.com/'):
        self.url = url
        self.api_key = api_key

    def get_loc_data(self, city):
        # Получаем так называемый ключ локации города
        request = requests.get(
            url=f'{self.url}locations/v1/cities/search',
            params={
                    'apikey': self.api_key,
                    'q':city,
                    'language': 'en-us',
                    'details': 'true',
                           }
                           )
        result = request.json()
        loc_key = result[0]['Key']
        loc_lat = result[0]['GeoPosition']['Latitude']
        loc_lon = result[0]['GeoPosition']['Longitude']
        return loc_key, loc_lat, loc_lon

    def get_weather(self, city, days):
        # С помощью ключа локации узнаем погоду в городе
        location_key, loc_lat, loc_lon = self.get_loc_data(city)
        request = requests.get(url=f'{self.url}forecasts/v1/daily/{days}day/{location_key}',
                           params={
                               'apikey': self.api_key,
                               'language': 'en-us',
                               'details': 'true',
                               'metric': 'true'
                           })
        result = request.json()
        data = []
        for day in result['DailyForecasts']:
            for day_part in ['Day', 'Night']:
                data.append(
                    {
                            'loc': city,
                            'lat': loc_lat,
                            'lon': loc_lon,
                            'date': datetime.fromisoformat(day['Date']).date(),
                            'time_of_day': day_part,
                            'temperature': (day['Temperature']['Minimum']['Value'] +
                                day['Temperature']['Maximum']['Value']) / 2,
                            'precipitation': day[day_part]['RainProbability'],
                            'humidity': day[day_part]['RelativeHumidity']['Average'],
                            'wind_speed': day[day_part]['Wind']['Speed']['Value']
                }
                )
        return data
