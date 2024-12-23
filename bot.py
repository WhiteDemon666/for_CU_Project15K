from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio

from api_keys import BOT_API, ACCU_API
from api import AccuWeather


BOT_TOKEN = BOT_API
API_KEY = ACCU_API

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class WeatherStates(StatesGroup):
    start_city = State()
    end_city = State()
    intermediate_cities = State()
    days = State()


# Создаем кнопки (inline)
def create_days_buttons():
    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text="1 день", callback_data="1"))
    keyboard.add(types.InlineKeyboardButton(text="5 дней", callback_data="5"))
    return keyboard.as_markup()


# Обработчик команды /start и /help
@dp.message(Command("start", "help"))
async def start_command(message: types.Message, state: FSMContext):
    await message.answer(
        "Привет, я могу помочь тебе узнать прогноз погоды по маршруту.\n"
        "Мои команды:\n\n"
        "/weather - Получить прогноз погоды для маршрута\n"
        "Введите начальный город, конечный и промежуточные города, тогда я покажу тебе прогноз погоды.\n\n"
        "Попробуй команду /help, чтобы получить список доступных команд."
    )


# Обработчик команды weather
@dp.message(Command("weather"))
async def weather_command(message: types.Message, state: FSMContext):
    await message.answer("Введите начальный город:")
    await state.set_state(WeatherStates.start_city)


# Обработчик для выбора количества дней
@dp.callback_query(lambda c: c.data in ["1", "5"])
async def process_days_selection(callback_query: types.CallbackQuery, state: FSMContext):
    days = int(callback_query.data)
    await state.update_data(days=days)
    await callback_query.answer(f"Вы выбрали {days} дня(ей) прогноза.")
    await bot.send_message(callback_query.from_user.id, "Введите конечный город:")
    await state.set_state(WeatherStates.end_city)


# Начальный город
@dp.message(WeatherStates.start_city)
async def process_start_city(message: types.Message, state: FSMContext):
    weather_api = AccuWeather(API_KEY)
    city_name = message.text.strip().lower()
    try:
        _, lat, lon = weather_api.get_loc_data(city_name)
        coordinates = (lat, lon)
        if coordinates is None:
            await message.answer(f"Город '{city_name.capitalize()}' не был найден. Пожалуйста, попробуйте снова.")
            return

        await state.update_data(start_city=city_name)
        await message.answer("Выберите на сколько дней вы хотите получить прогноз погоды:",
                             reply_markup=create_days_buttons())
        await state.set_state(WeatherStates.days)
    except ValueError as e:
        await message.answer(f"Ошибка: {str(e)}. Попробуйте снова.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте снова.")


# Конечный город
@dp.message(WeatherStates.end_city)
async def process_end_city(message: types.Message, state: FSMContext):
    weather_api = AccuWeather(API_KEY)
    data = await state.get_data()
    start_city = data["start_city"]
    end_city = message.text.strip().lower()

    if start_city == end_city:
        await message.answer("Ошибка: совпадение начальной и конечной точки маршрута! Введите другой конечный город:")
        return

    try:
        _, lat, lon = weather_api.get_loc_data(end_city)
        coordinates = (lat, lon)
        if coordinates is None:
            await message.answer(f"Город '{end_city.capitalize()}' не найден. Пожалуйста, попробуйте снова.")
            return

        await state.update_data(end_city=end_city)
        await message.answer("Введите промежуточные города через пробел (если их нет, напишите 'нет'):")
        await state.set_state(WeatherStates.intermediate_cities)
    except ValueError as e:
        await message.answer(f"Ошибка: {str(e)}. Попробуйте снова.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте снова.")


# Промежуточные города
@dp.message(WeatherStates.intermediate_cities)
async def process_intermediate_cities(message: types.Message, state: FSMContext):
    weather_api = AccuWeather(API_KEY)
    data = await state.get_data()
    start_city = data["start_city"]
    end_city = data["end_city"]
    intermediate_cities_input = message.text.strip().lower()

    if intermediate_cities_input == "нет":
        intermediate_cities = []
    else:
        intermediate_cities = [city.strip() for city in intermediate_cities_input.split() if city.strip()]

    if any(city in [start_city, end_city] for city in intermediate_cities):
        await message.answer(
            "Ошибка: промежуточные города не должны совпадать с начальным или конечным городом. Попробуйте еще раз:")
        return

    route = f"{start_city.capitalize()} -> "
    if intermediate_cities:
        route += " -> ".join([city.capitalize() for city in intermediate_cities]) + " -> "
    route += f"{end_city.capitalize()}"

    # Получаем количество дней из состояния
    days = data.get('days', 1)

    # Получаем координаты и прогноз погоды для каждого города
    try:
        cities = [start_city] + intermediate_cities + [end_city]
        weather_report = ""
        for city in cities:
            try:
                _, lat, lon = weather_api.get_loc_data(city)
                if lat is None or lon is None:
                    await message.answer(f"Город '{city.capitalize()}' не был найден. Пропускаем его.")
                    continue
                forecast = weather_api.get_weather(city, days)
                weather_report += f"Погода для города {city.capitalize()}:\n"
                for day in forecast:
                    if day['time_of_day'] == 'Day':
                        weather_report += (
                            f"Дата: {day['date']}\n"
                            f"Средняя температура: {round(day['temperature'],1)}°C\n"
                            f"Влажность: {day['humidity']}%\n"
                            f"Вероятность осадков: {day['precipitation']}%\n"
                            f"Скорость ветра: {day['wind_speed']} м/с\n\n"
                        )
            except Exception as e:
                await message.answer(f"Ошибка при получении данных для города '{city.capitalize()}': {str(e)}")

        await message.answer(f"Ваш маршрут: {route}\n\n{weather_report}")
    except Exception as e:
        await message.answer(f"Произошла ошибка при обработке маршрута: {str(e)}")

    await state.clear()


# Запускаем бота
if __name__ == "__main__":
    async def main():
        await dp.start_polling(bot)

    asyncio.run(main())