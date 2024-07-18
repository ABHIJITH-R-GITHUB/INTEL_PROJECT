from flask import Flask, render_template, request
import requests
import re

app = Flask(__name__)

def ask_user_location():
    return request.form.get('location')

def convert_location_to_coordinates(api_key, location):
    base_url = "https://api.tomtom.com"
    version_number = "2"
    ext = "json"

    endpoint = f"{base_url}/search/{version_number}/geocode/{location}.{ext}"
    params = {
        'key': api_key,
        'limit': 1
    }

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()

        data = response.json()

        if 'results' in data and data['results']:
            lat = data['results'][0]['position']['lat']
            lon = data['results'][0]['position']['lon']
            return lat, lon
        else:
            print(f"Coordinates not found for location: {location}")
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return None, None
    except ValueError as e:
        print(f"ValueError: {e}")
        print(f"Response Content: {response.text}")
        return None, None
    except Exception as e:
        print(f"Error: {e}")
        return None, None

def find_nearest_places(latitude, longitude, place_type, initial_radius=5000, max_radius=50000, step=5000):
    place_types = {
        "hospital": "hospital",
        "educational institution": "school"
    }

    overpass_url = "http://overpass-api.de/api/interpreter"
    radius = initial_radius
    all_places = []

    while radius <= max_radius:
        overpass_query = f"""
            [out:json];
            node["amenity"="{place_types[place_type]}"](around:{radius},{latitude},{longitude});
            out body;
            """
        try:
            response = requests.get(overpass_url, params={'data': overpass_query})
            response.raise_for_status()

            data = response.json()
            places = []

            for element in data['elements']:
                place = {
                    'name': element['tags'].get('name', 'N/A'),
                    'address': element['tags'].get('addr:full', 'N/A'),
                    'latitude': element['lat'],
                    'longitude': element['lon']
                }
                places.append(place)

            if len(places) >= 10:
                return places

            all_places.extend(places)
            radius += step

        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            return None
        except ValueError as e:
            print(f"ValueError: {e}")
            print(f"Response Content: {response.text}")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    return all_places

def convert_coords_to_address(api_key, latitude, longitude):
    base_url = "https://api.tomtom.com"
    version_number = "2"
    position = f"{latitude},{longitude}"
    ext = "json"

    endpoint = f"{base_url}/search/{version_number}/reverseGeocode/{position}.{ext}"
    params = {
        'key': api_key,
        'language': 'en-US',
        'radius': 1000,  # You can adjust this radius if needed
        'returnSpeedLimit': True
    }

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()

        data = response.json()

        # Print raw response for debugging
        print(f"Raw response: {data}")

        if 'addresses' in data and data['addresses']:
            address = data['addresses'][0]['address']['freeformAddress']
            return address if address else 'Address not found'
        else:
            return 'Address not found'

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return 'Address not found'
    except ValueError as e:
        print(f"ValueError: {e}")
        print(f"Response Content: {response.text}")
        return 'Address not found'
    except Exception as e:
        print(f"Error: {e}")
        return 'Address not found'

def rating_scrapper(place_name):
    API_KEY = ''  # Removed API key
    CSE_ID = ''  # Removed Custom Search Engine ID
    QUERY = f"{place_name} justdial ratings"
    url = f"https://www.googleapis.com/customsearch/v1?q={QUERY}&key={API_KEY}&cx={CSE_ID}"

    try:
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()
        search_results = data.get('items', [])

        rating_pattern = r"Rated\s+(\d+(\.\d+)?)"
        number_pattern = r"(\d+)\s+Customer Reviews"

        for result in search_results[:3]:
            if 'snippet' in result:
                snippet = result['snippet']

                rating_match = re.search(rating_pattern, snippet)
                number_match = re.search(number_pattern, snippet)

                if rating_match and number_match:
                    rating = float(rating_match.group(1))
                    number_of_reviews = int(number_match.group(1))
                    return rating, number_of_reviews

        print(f"No valid ratings found for {place_name} in the first 3 search results.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching rating search results: {e}")

    except KeyError as e:
        print(f"KeyError: {e}. Response: {response.text}")

    except Exception as e:
        print(f"Error: {e}")

    return None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        api_key = ''  # Removed API key

        choice = request.form.get('choice')
        place_type = "hospital" if choice == '1' else "educational institution"
        place_type_plural = "Hospitals" if choice == '1' else "Educational Institutions"

        user_location = ask_user_location()

        if user_location:
            latitude, longitude = convert_location_to_coordinates(api_key, user_location)

            if latitude is not None and longitude is not None:
                places = find_nearest_places(latitude, longitude, place_type.lower())
                if places:
                    results = []
                    for i, place in enumerate(places[:10]):  # Limit to 10 results
                        place_name = place['name']
                        rating, number_of_reviews = rating_scrapper(place_name)

                        address = place['address']
                        if address == 'N/A':
                            address = convert_coords_to_address(api_key, place['latitude'], place['longitude'])

                        result = {
                            'number': i + 1,
                            'name': place_name,
                            'address': address,
                            'latitude': place['latitude'],
                            'longitude': place['longitude'],
                            'rating': rating,
                            'reviews': number_of_reviews
                        }
                        results.append(result)

                    return render_template('results.html', location=user_location, results=results, place_type=place_type_plural)
                else:
                    return render_template('error.html', message=f"No {place_type_plural} details found from Overpass API.")
            else:
                return render_template('error.html', message=f"Failed to fetch coordinates for location: {user_location}")

        else:
            return render_template('error.html', message="No user location provided.")

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
