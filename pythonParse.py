import streamlit as st
import pandas as pd
import json
import os
from googleapiclient.discovery import build
import time
import re
from datetime import datetime, timedelta

# Настройки приложения
st.set_page_config(page_title="YouTube Channel Parser", page_icon="📺", layout="wide")

# Файл для хранения данных
DATA_FILE = "youtube_channels.json"
API_KEYS_FILE = "api_keys.json"
API_USAGE_FILE = "api_usage.json"

# Глобальная переменная для логирования API запросов
if 'api_logs' not in st.session_state:
    st.session_state.api_logs = []
if 'current_api_key' not in st.session_state:
    st.session_state.current_api_key = ""

# Функция для загрузки данных из JSON
def load_channels():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            st.error(f"Ошибка декодирования JSON: {e}. Проверьте файл {DATA_FILE}.")
            return []
    return []

# Функция для сохранения данных в JSON
def save_channels(channels):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)

# Функция для загрузки API-ключей
def load_api_keys():
    if os.path.exists(API_KEYS_FILE):
        try:
            with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

# Функция для сохранения API-ключей
def save_api_keys(keys):
    with open(API_KEYS_FILE, 'w', encoding='utf-8') as f:
        json.dump(keys, f, ensure_ascii=False, indent=2)

# Функция для загрузки использования API
def load_api_usage():
    if os.path.exists(API_USAGE_FILE):
        try:
            with open(API_USAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

# Функция для сохранения использования API
def save_api_usage(usage_data):
    with open(API_USAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(usage_data, f, ensure_ascii=False, indent=2)

# Функция для логирования API запросов
def log_api_request(request_type, query, cost=1):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {request_type}: '{query}' (стоимость: {cost})"
    st.session_state.api_logs.append(log_entry)
    if len(st.session_state.api_logs) > 50:  # Ограничиваем размер лога
        st.session_state.api_logs.pop(0)
    
    # Обновляем статистику использования
    usage_data = load_api_usage()
    today = datetime.now().strftime("%Y-%m-%d")
    key = st.session_state.current_api_key[:10] + "..." if st.session_state.current_api_key else "unknown"
    
    if key not in usage_data:
        usage_data[key] = {}
    if today not in usage_data[key]:
        usage_data[key][today] = 0
    
    usage_data[key][today] += cost
    save_api_usage(usage_data)

# Заголовок
st.title("📺 YouTube Channel Parser")
st.markdown("Введите настройки для поиска каналов и получите результаты прямо здесь!")

# Навигация по вкладкам
tab1, tab2, tab3 = st.tabs(["🔍 Поиск каналов", "📋 Сохранённые каналы", "🔑 API-ключи"])

with tab1:
    # Состояние для остановки поиска
    if 'stop_search' not in st.session_state:
        st.session_state.stop_search = False
    if 'channels_data' not in st.session_state:
        st.session_state.channels_data = []
    if 'search_started' not in st.session_state:
        st.session_state.search_started = False

    # Форма для ввода параметров
    st.sidebar.header("Настройки поиска")
    
    # Режим поиска
    search_mode = st.sidebar.selectbox(
        "🔍 Режим поиска:",
        ["По названию канала", "По тегам канала", "По видео"],
        key="search_mode",
        help="Выберите способ поиска каналов"
    )
    
    if search_mode == "По названию канала":
        search_input = st.sidebar.text_area(
            "Ключевые слова (одно на строку или через |):",
            value="python|programming|coding|tech",
            key="search_input",
            help="Пример: python|programming|coding"
        )
        search_queries = [q.strip() for q in search_input.split('|') if q.strip()]
    
    elif search_mode == "По тегам канала":
        search_input = st.sidebar.text_area(
            "Теги каналов (одно на строку или через |):",
            value="python|programming|coding|tech",
            key="search_input_tags",
            help="Пример: python|programming|javascript"
        )
        search_queries = [q.strip() for q in search_input.split('|') if q.strip()]
    
    else:  # По видео
        search_input = st.sidebar.text_area(
            "Темы видео для поиска (одно на строку или через |):",
            value="python tutorial|programming basics|coding interview",
            key="search_input_videos",
            help="Пример: python tutorial|react js|machine learning"
        )
        search_queries = [q.strip() for q in search_input.split('|') if q.strip()]

    max_results_per_query = st.sidebar.number_input(
        "Макс. результатов за запрос (1-50):",
        min_value=1,
        max_value=50,
        value=25,
        key="max_results",
        help="Меньше значение = меньше расход квоты API"
    )

    min_subscribers = st.sidebar.number_input(
        "Минимальное количество подписчиков:",
        min_value=1000,
        value=100000,
        key="min_subscribers",
        help="Только каналы с этим и большим числом подпищиков"
    )

    max_subscribers = st.sidebar.number_input(
        "Максимальное количество подписчиков (0 = без ограничения):",
        min_value=0,
        value=0,
        key="max_subscribers",
        help="Каналы с не большим этим числом (0 — без верхнего лимита)"
    )

    target_channels = st.sidebar.number_input(
        "Целевое количество каналов (минимум):",
        min_value=10,
        max_value=500,
        value=100,
        key="target_channels",
        help="Поиск продолжится, пока не найдётся столько каналов"
    )

    # Выбор API-ключа
    api_keys = load_api_keys()
    if api_keys:
        selected_key = st.sidebar.selectbox("Выберите API-ключ:", [k['key'] for k in api_keys], key="select_key")
        api_key = next((k['key'] for k in api_keys if k['key'] == selected_key), "")
    else:
        api_key = st.sidebar.text_input(
            "YouTube API Key:",
            value="",
            type="password",
            key="api_key",
            help="Ваш ключ из Google Cloud Console"
        )

    # Кнопки запуска и остановки
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_pressed = st.button("Запустить поиск", key="start_button")
    with col2:
        stop_pressed = st.button("Стоп", key="stop_button")

    if start_pressed:
        st.session_state.stop_search = False
        st.session_state.search_started = True
        st.session_state.channels_data = []

    if stop_pressed:
        st.session_state.stop_search = True
        # Сохранение уже найденных каналов при остановке
        if st.session_state.channels_data:
            existing_channels = load_channels()
            existing_titles = {ch.get('title', '').lower() for ch in existing_channels}
            added_count = 0
            duplicates_count = 0
            for ch in st.session_state.channels_data:
                if ch['title'].lower() not in existing_titles:
                    existing_channels.append(ch)
                    existing_titles.add(ch['title'].lower())
                    added_count += 1
                else:
                    duplicates_count += 1
            if added_count > 0:
                save_channels(existing_channels)
                st.success(f"✅ Сохранено {added_count} новых каналов при остановке. Дубликатов: {duplicates_count}")
            else:
                st.warning(f"⚠️ Все каналы — дубликаты ({duplicates_count}). Ничего не добавлено.")
            st.session_state.channels_data = []  # Очистка после сохранения

    if api_key and search_queries and st.session_state.search_started:
        # Устанавливаем текущий API ключ для логирования
        st.session_state.current_api_key = api_key
        
        with st.spinner("Поиск каналов... Это может занять время (учтите квоту API)"):
            try:
                youtube = build('youtube', 'v3', developerKey=api_key)
                existing_channels = load_channels()
                existing_channel_ids = {ch.get('channel_id', '') for ch in existing_channels if ch.get('channel_id')}
                existing_titles = {ch.get('title', '').lower() for ch in existing_channels}

                def get_channel_details(channel_id):
                    log_api_request("Получение данных канала", f"Channel ID: {channel_id}", 1)
                    request = youtube.channels().list(part='snippet,statistics,brandingSettings', id=channel_id)
                    response = request.execute()
                    if response['items']:
                        item = response['items'][0]
                        title = item['snippet']['title']
                        description = item['snippet']['description']
                        subscribers = int(item['statistics'].get('subscriberCount', 0))
                        
                        # Получаем теги канала
                        channel_tags = []
                        if 'brandingSettings' in item and 'channel' in item['brandingSettings']:
                            keywords = item['brandingSettings']['channel'].get('keywords', '')
                            if keywords:
                                channel_tags = [tag.strip() for tag in keywords.split(',')]
                        
                        contacts = extract_contacts(description)
                        return {
                            'title': title,
                            'channel_id': channel_id,  # Добавляем ID канала для точной проверки дубликатов
                            'channel_url': f"https://www.youtube.com/channel/{channel_id}",
                            'subscribers': subscribers,
                            'description': description,
                            'contacts': contacts.get('contacts', 'Не найдено'),
                            'viewed': False,
                            'tags': ', '.join(channel_tags) if channel_tags else 'Нет тегов'
                        }
                    return None

                def extract_contacts(description):
                    contacts = {'contacts': 'Не найдено'}
                    if description:
                        email = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', description)
                        links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', description)
                        telegram = re.findall(r'@[\w]+', description)
                        
                        contacts_list = []
                        if email:
                            contacts_list.append(f"Email: {email.group()}")
                        if links:
                            contacts_list.extend([f"Ссылка: {link}" for link in links])
                        if telegram:
                            contacts_list.extend([f"Telegram: {t}" for t in telegram])
                        
                        if contacts_list:
                            contacts = {'contacts': '; '.join(contacts_list)}
                    return contacts

                def search_channels_by_name(queries, max_results, target):
                    current_query_index = 0
                    processed_channels = set()
                    
                    while len(st.session_state.channels_data) < target and not st.session_state.stop_search:
                        query = queries[current_query_index].strip()
                        if not query:
                            current_query_index = (current_query_index + 1) % len(queries)
                            continue
                        st.write(f"🔍 Поиск каналов по названию: '{query}' (найдено: {len(st.session_state.channels_data)})")
                        
                        next_page_token = None
                        page_count = 0
                        while next_page_token is not None or page_count == 0:
                            if len(st.session_state.channels_data) >= target or st.session_state.stop_search:
                                break
                            
                            log_api_request("Поиск каналов", query, 100)
                            request = youtube.search().list(
                                part='snippet',
                                q=query,
                                type='channel',
                                maxResults=max_results,
                                pageToken=next_page_token
                            )
                            try:
                                response = request.execute()
                                for item in response['items']:
                                    if len(st.session_state.channels_data) >= target or st.session_state.stop_search:
                                        break
                                    channel_id = item['snippet']['channelId']
                                    if channel_id not in processed_channels and channel_id not in existing_channel_ids:
                                        channel_details = get_channel_details(channel_id)
                                        if channel_details and channel_details['subscribers'] >= min_subscribers:
                                            if max_subscribers > 0 and channel_details['subscribers'] > max_subscribers:
                                                continue
                                            st.session_state.channels_data.append(channel_details)
                                            processed_channels.add(channel_id)
                                            st.write(f"✅ {channel_details['title']} ({channel_details['subscribers']} подписчиков)")
                                
                                next_page_token = response.get('nextPageToken')
                                page_count += 1
                                time.sleep(1)
                            except Exception as e:
                                if 'quotaExceeded' in str(e):
                                    st.error("❌ Квота API исчерпана! Подождите 24 часа или увеличьте квоту.")
                                    return
                                else:
                                    st.error(f"Ошибка API: {e}")
                                    return
                        
                        current_query_index = (current_query_index + 1) % len(queries)
                        if current_query_index == 0:
                            st.warning("Обход всех запросов завершён. Больше каналов не найдено.")
                            break

                def search_channels_by_tags(queries, max_results, target):
                    current_query_index = 0
                    processed_channels = set()
                    
                    while len(st.session_state.channels_data) < target and not st.session_state.stop_search:
                        query = queries[current_query_index].strip()
                        if not query:
                            current_query_index = (current_query_index + 1) % len(queries)
                            continue
                        st.write(f"🔍 Поиск каналов по тегам: '{query}' (найдено: {len(st.session_state.channels_data)})")
                        
                        next_page_token = None
                        page_count = 0
                        while next_page_token is not None or page_count == 0:
                            if len(st.session_state.channels_data) >= target or st.session_state.stop_search:
                                break
                            
                            log_api_request("Поиск по тегам", query, 100)
                            request = youtube.search().list(
                                part='snippet',
                                q=query,
                                type='channel',
                                maxResults=max_results,
                                pageToken=next_page_token
                            )
                            try:
                                response = request.execute()
                                for item in response['items']:
                                    if len(st.session_state.channels_data) >= target or st.session_state.stop_search:
                                        break
                                    channel_id = item['snippet']['channelId']
                                    if channel_id not in processed_channels and channel_id not in existing_channel_ids:
                                        channel_details = get_channel_details_with_tags(channel_id, query)
                                        if channel_details and channel_details['subscribers'] >= min_subscribers:
                                            if max_subscribers > 0 and channel_details['subscribers'] > max_subscribers:
                                                continue
                                            st.session_state.channels_data.append(channel_details)
                                            processed_channels.add(channel_id)
                                            st.write(f"✅ {channel_details['title']} ({channel_details['subscribers']} подписчиков)")
                                
                                next_page_token = response.get('nextPageToken')
                                page_count += 1
                                time.sleep(1)
                            except Exception as e:
                                if 'quotaExceeded' in str(e):
                                    st.error("❌ Квота API исчерпана! Подождите 24 часа или увеличьте квоту.")
                                    return
                                else:
                                    st.error(f"Ошибка API: {e}")
                                    return
                        
                        current_query_index = (current_query_index + 1) % len(queries)
                        if current_query_index == 0:
                            st.warning("Обход всех тегов завершён. Больше каналов не найдено.")
                            break

                def search_channels_by_videos(queries, max_results, target):
                    current_query_index = 0
                    processed_channels = set()
                    
                    while len(st.session_state.channels_data) < target and not st.session_state.stop_search:
                        query = queries[current_query_index].strip()
                        if not query:
                            current_query_index = (current_query_index + 1) % len(queries)
                            continue
                        st.write(f"🔍 Поиск каналов через видео: '{query}' (найдено: {len(st.session_state.channels_data)})")
                        
                        next_page_token = None
                        page_count = 0
                        while next_page_token is not None or page_count == 0:
                            if len(st.session_state.channels_data) >= target or st.session_state.stop_search:
                                break
                            
                            log_api_request("Поиск видео", query, 100)
                            request = youtube.search().list(
                                part='snippet',
                                q=query,
                                type='video',
                                maxResults=max_results,
                                pageToken=next_page_token,
                                order='relevance'
                            )
                            try:
                                response = request.execute()
                                for item in response['items']:
                                    if len(st.session_state.channels_data) >= target or st.session_state.stop_search:
                                        break
                                    channel_id = item['snippet']['channelId']
                                    if channel_id not in processed_channels and channel_id not in existing_channel_ids:
                                        # Получаем теги видео
                                        video_tags = get_video_tags(item['id']['videoId'])
                                        channel_details = get_channel_details(channel_id)
                                        if channel_details and channel_details['subscribers'] >= min_subscribers:
                                            if max_subscribers > 0 and channel_details['subscribers'] > max_subscribers:
                                                continue
                                            # Добавляем информацию о видео и его тегах
                                            channel_details['found_via_video'] = item['snippet']['title'][:80] + "..."
                                            channel_details['video_tags'] = video_tags
                                            
                                            st.session_state.channels_data.append(channel_details)
                                            processed_channels.add(channel_id)
                                            st.write(f"✅ {channel_details['title']} ({channel_details['subscribers']} подписчиков) - через видео: {item['snippet']['title'][:50]}...")
                                
                                next_page_token = response.get('nextPageToken')
                                page_count += 1
                                time.sleep(1)
                            except Exception as e:
                                if 'quotaExceeded' in str(e):
                                    st.error("❌ Квота API исчерпана! Подождите 24 часа или увеличьте квоту.")
                                    return
                                else:
                                    st.error(f"Ошибка API: {e}")
                                    return
                        
                        current_query_index = (current_query_index + 1) % len(queries)
                        if current_query_index == 0:
                            st.warning("Обход всех тем видео завершён. Больше каналов не найдено.")
                            break

                def get_video_tags(video_id):
                    """Получает теги видео"""
                    try:
                        log_api_request("Получение тегов видео", f"Video ID: {video_id}", 1)
                        request = youtube.videos().list(part='snippet', id=video_id)
                        response = request.execute()
                        if response['items']:
                            tags = response['items'][0]['snippet'].get('tags', [])
                            return ', '.join(tags[:10]) if tags else 'Нет тегов'  # Первые 10 тегов
                        return 'Нет тегов'
                    except Exception as e:
                        return 'Ошибка получения тегов'

                def get_channel_details_with_tags(channel_id, search_tag):
                    """Получает детали канала и проверяет соответствие тегам"""
                    log_api_request("Получение данных канала с тегами", f"Channel ID: {channel_id}", 1)
                    request = youtube.channels().list(part='snippet,statistics,brandingSettings', id=channel_id)
                    response = request.execute()
                    if response['items']:
                        item = response['items'][0]
                        title = item['snippet']['title']
                        description = item['snippet']['description']
                        subscribers = int(item['statistics'].get('subscriberCount', 0))
                        
                        # Получаем теги канала (keywords)
                        channel_tags = []
                        if 'brandingSettings' in item and 'channel' in item['brandingSettings']:
                            keywords = item['brandingSettings']['channel'].get('keywords', '')
                            if keywords:
                                channel_tags = [tag.strip() for tag in keywords.split(',')]
                        
                        # Проверяем, содержит ли канал искомый тег
                        search_tag_lower = search_tag.lower()
                        tag_match = any(search_tag_lower in tag.lower() for tag in channel_tags) or search_tag_lower in description.lower()
                        
                        if tag_match:
                            contacts = extract_contacts(description)
                            return {
                                'title': title,
                                'channel_id': channel_id,
                                'channel_url': f"https://www.youtube.com/channel/{channel_id}",
                                'subscribers': subscribers,
                                'description': description,
                                'contacts': contacts.get('contacts', 'Не найдено'),
                                'viewed': False,
                                'tags': ', '.join(channel_tags) if channel_tags else 'Нет тегов'
                            }
                    
                    return None

                # Запуск поиска в зависимости от выбранного режима
                if search_mode == "По названию канала":
                    search_channels_by_name(search_queries, max_results_per_query, target_channels)
                elif search_mode == "По тегам канала":
                    search_channels_by_tags(search_queries, max_results_per_query, target_channels)
                else:  # По видео
                    search_channels_by_videos(search_queries, max_results_per_query, target_channels)

                # Сохранение при завершении поиска
                if st.session_state.channels_data:
                    # Исправленная проверка дубликатов - используем channel_id для точного сравнения
                    existing_channels = load_channels()
                    existing_channel_ids = {ch.get('channel_id', '') for ch in existing_channels if ch.get('channel_id')}
                    
                    added_count = 0
                    duplicates_count = 0
                    for ch in st.session_state.channels_data:
                        channel_id = ch.get('channel_id', '')
                        if channel_id and channel_id not in existing_channel_ids:
                            existing_channels.append(ch)
                            existing_channel_ids.add(channel_id)
                            added_count += 1
                        else:
                            duplicates_count += 1

                    if added_count > 0:
                        save_channels(existing_channels)
                        st.success(f"✅ Сохранено {added_count} новых каналов. Дубликатов: {duplicates_count}")
                    else:
                        st.warning(f"⚠️ Все каналы — дубликаты ({duplicates_count}). Ничего не добавлено.")
                    
                    # Отображение новых результатов
                    df_new = pd.DataFrame(st.session_state.channels_data)
                    st.subheader("Новые найденные каналы:")
                    st.dataframe(df_new, use_container_width=True)
                    
                    # Скачивание CSV новых
                    csv_new = df_new.to_csv(index=False, encoding='utf-8')
                    st.download_button(
                        label="📥 Скачать новые CSV",
                        data=csv_new,
                        file_name=f'new_youtube_channels_{added_count}.csv',
                        mime='text/csv'
                    )
                    st.session_state.channels_data = []  # Очистка после сохранения
                else:
                    st.warning("⚠️ Каналы не найдены. Попробуйте другие ключевые слова или уменьшите мин. подписчиков.")

            except Exception as e:
                st.error(f"Общая ошибка: {e}")
    
    # Консоль с логами API запросов
    if st.session_state.api_logs:
        with st.expander("📊 Консоль API запросов", expanded=False):
            st.text_area("Лог запросов:", value='\n'.join(st.session_state.api_logs[-20:]), height=200, disabled=True)
            if st.button("🗑️ Очистить лог", key="clear_log"):
                st.session_state.api_logs = []
                st.rerun()

with tab2:
    st.header("📋 Сохранённые каналы")
    
    existing_channels = load_channels()
    
    if existing_channels:
        # Создаем красивую панель управления с кнопками
        st.markdown("### 🎛️ Панель управления")
        
        # Размещаем кнопки в красивом макете
        button_col1, button_col2, button_col3, stats_col = st.columns([1.5, 1.5, 1.5, 2])
        
        with button_col1:
            refresh_button = st.button("🔄 Обновить", key="refresh_button", use_container_width=True)
        with button_col2:
            save_button = st.button("💾 Сохранить", key="save_button", use_container_width=True, type="primary")
        with button_col3:
            delete_button = st.button("🗑️ Удалить выбранные", key="delete_button", use_container_width=True)
        
        # Статистика в правой части
        with stats_col:
            df = pd.DataFrame(existing_channels)
            viewed_count = df.get('viewed', pd.Series([False] * len(df))).sum()
            total_count = len(df)
            st.metric("📊 Статистика", f"{viewed_count}/{total_count} просмотрено")

        st.divider()  # Красивый разделитель

        if refresh_button:
            st.rerun()  # Перезагрузка страницы для обновления данных

        # Добавляем колонку для удаления (чекбокс)
        df['delete'] = False
        
        # Редактируемая таблица с чекбоксом для "viewed", "delete" и ссылкой
        st.subheader("📋 Таблица каналов")
        edited_df = st.data_editor(
            df,
            column_config={
                "channel_url": st.column_config.LinkColumn(
                    "🔗 Ссылка",
                    display_text="Перейти",
                    help="Кликните для открытия YouTube-канала"
                ),
                "viewed": st.column_config.CheckboxColumn(
                    "👁️ Просмотрено",
                    default=False,
                    required=False
                ),
                "delete": st.column_config.CheckboxColumn(
                    "❌ Удалить",
                    default=False,
                    required=False
                ),
                "title": st.column_config.TextColumn("📺 Название", width="medium"),
                "subscribers": st.column_config.NumberColumn("👥 Подписчики", format="%d"),
                "description": st.column_config.TextColumn("📝 Описание", width="large"),
                "contacts": st.column_config.TextColumn("📞 Контакты", width="medium"),
                "tags": st.column_config.TextColumn("🏷️ Теги", width="medium"),
                "found_via_video": st.column_config.TextColumn("📹 Найден через видео", width="medium"),
                "video_tags": st.column_config.TextColumn("🎬 Теги видео", width="medium")
            },
            use_container_width=True,
            hide_index=False,
            column_order=["title", "channel_url", "subscribers", "viewed", "delete", "description", "contacts", "tags", "found_via_video", "video_tags"]
        )
        
        # Логика сохранения изменений
        if save_button:
            updated_df = edited_df.drop(columns=['delete'])
            updated_channels = updated_df.to_dict('records')
            save_channels(updated_channels)
            st.success("✅ Изменения сохранены!")
            st.rerun()
        
        # Логика удаления выбранных строк
        if delete_button:
            to_delete = edited_df[edited_df['delete'] == True]
            if not to_delete.empty:
                updated_df = edited_df[~edited_df['delete']].drop(columns=['delete'])
                updated_channels = updated_df.to_dict('records')
                save_channels(updated_channels)
                st.success(f"✅ Удалено {len(to_delete)} каналов!")
                st.rerun()
            else:
                st.warning("⚠️ Не выбраны каналы для удаления!")
        
        # Скачивание полного CSV
        st.markdown("### 📥 Экспорт данных")
        csv_full = edited_df.drop(columns=['delete']).to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📄 Скачать все каналы (CSV)",
            data=csv_full,
            file_name=f'youtube_channels_{total_count}_records.csv',
            mime='text/csv',
            use_container_width=True
        )
        
    else:
        st.info("📭 Пока нет сохранённых каналов. Запустите поиск в первой вкладке!")

with tab3:
    st.header("🔑 Управление API-ключами")
    
    # Форма добавления нового ключа
    st.markdown("### ➕ Добавить новый ключ")
    
    add_col1, add_col2, add_col3 = st.columns([2, 2, 1])
    with add_col1:
        new_key = st.text_input("🔑 API-ключ:", type="password", key="new_key_input", placeholder="Введите YouTube API ключ")
    with add_col2:
        new_key_name = st.text_input("🏷️ Название:", key="new_key_name", placeholder="Например: Основной ключ")
    with add_col3:
        st.markdown("<br>", unsafe_allow_html=True)  # Отступ для выравнивания
        add_key_button = st.button("✅ Добавить", key="add_key_button", use_container_width=True, type="primary")
    
    if add_key_button:
        if new_key:
            api_keys = load_api_keys()
            api_keys.append({"name": new_key_name or "Без названия", "key": new_key})
            save_api_keys(api_keys)
            st.success("✅ API-ключ успешно добавлен!")
            st.rerun()
        else:
            st.error("❌ Необходимо ввести API-ключ!")
    
    st.divider()
    
    # Управление существующими ключами
    api_keys = load_api_keys()
    
    if api_keys:
        st.markdown("### 📋 Список API-ключей")
        
        # Панель управления ключами
        manage_col1, manage_col2, stats_col = st.columns([1.5, 1.5, 2])
        
        with manage_col1:
            save_changes_button = st.button("💾 Сохранить изменения", key="save_changes_keys", use_container_width=True, type="primary")
        with manage_col2:
            delete_selected_keys = st.button("🗑️ Удалить выбранные", key="delete_selected_keys", use_container_width=True)
        with stats_col:
            st.metric("📊 Всего ключей", len(api_keys))
        
        # Отображение статистики использования API
        st.markdown("### 📈 Статистика использования API")
        usage_data = load_api_usage()
        if usage_data:
            usage_df = []
            for key_short, dates in usage_data.items():
                for date, requests in dates.items():
                    usage_df.append({
                        'API ключ': key_short,
                        'Дата': date,
                        'Запросов': requests,
                        'Квота %': f"{min(100, (requests/10000)*100):.1f}%"
                    })
            
            if usage_df:
                df_usage = pd.DataFrame(usage_df)
                st.dataframe(df_usage, use_container_width=True, hide_index=True)
                
                # Показываем сводную статистику за сегодня
                today = datetime.now().strftime("%Y-%m-%d")
                today_usage = sum(dates.get(today, 0) for dates in usage_data.values())
                
                col_usage1, col_usage2, col_usage3 = st.columns(3)
                with col_usage1:
                    st.metric("📅 Сегодня использовано", today_usage)
                with col_usage2:
                    st.metric("🔋 Осталось квоты", max(0, 10000 - today_usage))
                with col_usage3:
                    quota_percent = min(100, (today_usage/10000)*100)
                    st.metric("📊 Квота использована", f"{quota_percent:.1f}%")
            else:
                st.info("Нет данных об использовании API")
        else:
            st.info("Нет данных об использовании API")
        
        # Добавляем колонку для удаления
        keys_df = pd.DataFrame(api_keys)
        keys_df['delete'] = False
        
        # Редактируемая таблица ключей
        edited_keys_df = st.data_editor(
            keys_df,
            column_config={
                "name": st.column_config.TextColumn("🏷️ Название", width="medium"),
                "key": st.column_config.TextColumn("🔑 API-ключ", width="large"),
                "delete": st.column_config.CheckboxColumn("❌ Удалить", default=False)
            },
            use_container_width=True,
            hide_index=True,
            column_order=["name", "key", "delete"]
        )
        
        # Логика сохранения изменений ключей
        if save_changes_button:
            updated_keys_df = edited_keys_df.drop(columns=['delete'])
            updated_keys = updated_keys_df.to_dict('records')
            save_api_keys(updated_keys)
            st.success("✅ Изменения в API-ключах сохранены!")
            st.rerun()
        
        # Логика удаления выбранных ключей
        if delete_selected_keys:
            keys_to_delete = edited_keys_df[edited_keys_df['delete'] == True]
            if not keys_to_delete.empty:
                remaining_keys_df = edited_keys_df[~edited_keys_df['delete']].drop(columns=['delete'])
                remaining_keys = remaining_keys_df.to_dict('records')
                save_api_keys(remaining_keys)
                st.success(f"✅ Удалено {len(keys_to_delete)} API-ключей!")
                st.rerun()
            else:
                st.warning("⚠️ Не выбраны ключи для удаления!")
        
    else:
        st.info("📭 Нет сохранённых API-ключей. Добавьте первый!")

# Инструкции
with st.expander("ℹ️ Инструкции"):
    st.markdown("""
    1. **Установка**: Установите Streamlit и зависимости:  
       `pip install streamlit google-api-python-client pandas`
    2. **Запуск**: Сохраните код в файл `app.py` и запустите:  
       `streamlit run app.py`
    3. **API-ключ**: Получите в [Google Cloud Console](https://console.cloud.google.com/) (включите YouTube Data API v3).
    4. **Квота**: Учитывайте лимит 10k единиц/день. Для большего — запросите увеличение.
    5. **Сохранение**: Данные хранятся в `youtube_channels.json`. Дубликаты пропускаются по названию.
    6. **Локально**: Приложение работает в браузере (localhost:8501), без сервера.
    """)