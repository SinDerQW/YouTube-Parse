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
    search_input = st.sidebar.text_area(
        "Ключевые слова (одно на строку или через запятую):",
        value="python,programming,coding,tech",
        key="search_input",
        help="Пример: python,programming"
    )
    # Обработка ввода: разделяем по запятым или новым строкам
    search_queries = [q.strip() for q in search_input.replace(',', '\n').splitlines() if q.strip()]

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
        with st.spinner("Поиск каналов... Это может занять время (учтите квоту API)"):
            try:
                youtube = build('youtube', 'v3', developerKey=api_key)
                existing_channels = load_channels()
                existing_titles = {ch.get('title', '').lower() for ch in existing_channels}

                def get_channel_details(channel_id):
                    request = youtube.channels().list(part='snippet,statistics', id=channel_id)
                    response = request.execute()
                    if response['items']:
                        item = response['items'][0]
                        title = item['snippet']['title']
                        description = item['snippet']['description']
                        subscribers = int(item['statistics'].get('subscriberCount', 0))
                        contacts = extract_contacts(description)
                        return {
                            'title': title,
                            'channel_url': f"https://www.youtube.com/channel/{channel_id}",
                            'subscribers': subscribers,
                            'description': description,
                            'contacts': contacts.get('contacts', 'Не найдено'),
                            'viewed': False  # По умолчанию не просмотрено
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

                def search_channels(queries, max_results, target):
                    current_query_index = 0
                    while len(st.session_state.channels_data) < target and not st.session_state.stop_search:
                        query = queries[current_query_index].strip()
                        if not query:
                            current_query_index = (current_query_index + 1) % len(queries)
                            continue
                        st.write(f"🔍 Поиск по: '{query}' (найдено: {len(st.session_state.channels_data)})")
                        
                        next_page_token = None
                        page_count = 0
                        while next_page_token is not None or page_count == 0:
                            if len(st.session_state.channels_data) >= target or st.session_state.stop_search:
                                break
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
                                    channel_details = get_channel_details(channel_id)
                                    if channel_details and channel_details['subscribers'] >= min_subscribers:
                                        if max_subscribers > 0 and channel_details['subscribers'] > max_subscribers:
                                            continue  # Пропускаем, если превышает максимум
                                        if channel_details['title'].lower() not in existing_titles:
                                            st.session_state.channels_data.append(channel_details)
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

                search_channels(search_queries, max_results_per_query, target_channels)

                # Сохранение при завершении поиска
                if st.session_state.channels_data:
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

with tab2:
    st.header("📋 Сохранённые каналы")
    
    # Разделяем кнопки на три отдельные
    col1, col2, col3 = st.columns(3)
    with col1:
        refresh_button = st.button("Обновить данные", key="refresh_button")
    with col2:
        save_button = st.button("Сохранить изменения", key="save_button")
    with col3:
        delete_button = st.button("Удалить выбранные", key="delete_button")

    if refresh_button:
        st.rerun()  # Перезагрузка страницы для обновления данных

    existing_channels = load_channels()
    if existing_channels:
        df = pd.DataFrame(existing_channels)
        
        # Добавляем колонку для удаления (чекбокс)
        df['delete'] = False
        
        # Редактируемая таблица с чекбоксом для "viewed", "delete" и ссылкой
        st.subheader("Таблица сохранённых каналов")
        edited_df = st.data_editor(
            df,
            column_config={
                "channel_url": st.column_config.LinkColumn(
                    "Ссылка на канал",
                    display_text="Перейти на канал",
                    help="Кликните для открытия YouTube-канала"
                ),
                "viewed": st.column_config.CheckboxColumn(
                    "Просмотрено",
                    default=False,
                    required=False
                ),
                "delete": st.column_config.CheckboxColumn(
                    "Удалить?",
                    default=False,
                    required=False
                )
            },
            use_container_width=True,
            hide_index=False,
            column_order=["title", "channel_url", "subscribers", "viewed", "delete", "description", "contacts"]
        )
        
        # Логика сохранения изменений
        if save_button:
            updated_df = edited_df.drop(columns=['delete'])
            updated_channels = updated_df.to_dict('records')
            save_channels(updated_channels)
            st.success("Изменения сохранены!")
            st.rerun()
        
        # Логика удаления выбранных строк
        if delete_button:
            to_delete = edited_df[edited_df['delete'] == True]
            if not to_delete.empty:
                updated_df = edited_df[~edited_df['delete']].drop(columns=['delete'])
                updated_channels = updated_df.to_dict('records')
                save_channels(updated_channels)
                st.success(f"Удалено {len(to_delete)} строк!")
                st.rerun()
            else:
                st.warning("Не выбраны строки для удаления!")
        
    else:
        st.info("📭 Пока нет сохранённых каналов. Запустите поиск в первой вкладке!")

    # Статистика
    viewed_count = edited_df['viewed'].sum() if 'viewed' in edited_df.columns else 0
    total_count = len(edited_df) if 'edited_df' in locals() else 0
    st.metric("Всего каналов", total_count)
    st.metric("Просмотрено", viewed_count)
    
    # Скачивание полного CSV
    csv_full = edited_df.drop(columns=['delete']).to_csv(index=False, encoding='utf-8') if 'edited_df' in locals() else ""
    st.download_button(
        label="📥 Скачать все CSV",
        data=csv_full,
        file_name=f'all_youtube_channels_{total_count}.csv',
        mime='text/csv',
        disabled=not existing_channels
    )

with tab3:
    st.header("🔑 API-ключи")
    api_keys = load_api_keys()
    
    # Добавление нового ключа
    new_key = st.text_input("Новый API-ключ:", type="password", key="new_key_input")
    new_key_name = st.text_input("Имя ключа (опционально):", key="new_key_name")
    if st.button("Добавить ключ"):
        if new_key:
            api_keys.append({"name": new_key_name or "Без имени", "key": new_key})
            save_api_keys(api_keys)
            st.success("Ключ добавлен!")
            st.rerun()
        else:
            st.error("Введите ключ!")
    
    # Таблица API-ключей
    if api_keys:
        st.subheader("Список API-ключей")
        edited_keys = st.data_editor(
            api_keys,
            column_config={
                "name": "Имя",
                "key": st.column_config.TextColumn("Ключ", help="Скрытая часть ключа отображается как ...")
            },
            use_container_width=True,
            hide_index=True
        )
        
        if st.button("Сохранить изменения"):
            save_api_keys(edited_keys)
            st.success("Изменения сохранены!")
            st.rerun()
        
    else:
        st.info("Нет сохранённых ключей. Добавьте первый!")

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