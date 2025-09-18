import streamlit as st
import pandas as pd
import json
import os
from googleapiclient.discovery import build
import time
import re

# Настройки приложения
st.set_page_config(page_title="YouTube Channel Parser", page_icon="📺", layout="wide")

# Файл для хранения данных
DATA_FILE = "youtube_channels.json"

# Функция для загрузки данных из JSON (без кэширования для динамического обновления)
def load_channels():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.write("Отладка: Данные из JSON загружены успешно.", data[:2])  # Отладочный вывод первых двух записей
                return data
        except json.JSONDecodeError as e:
            st.error(f"Ошибка декодирования JSON: {e}. Проверьте файл {DATA_FILE}.")
            return []
    return []

# Функция для сохранения данных в JSON
def save_channels(channels):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)

# Заголовок
st.title("📺 YouTube Channel Parser")
st.markdown("Введите настройки для поиска каналов и получите результаты прямо здесь!")

# Навигация по вкладкам
tab1, tab2 = st.tabs(["🔍 Поиск каналов", "📋 Сохранённые каналы"])

with tab1:
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

    api_key = st.sidebar.text_input(
        "YouTube API Key:",
        value="",
        type="password",
        key="api_key",
        help="Ваш ключ из Google Cloud Console"
    )

    if st.sidebar.button("Запустить поиск", key="start_button"):
        if not api_key:
            st.error("Введите API-ключ!")
        elif not search_queries:
            st.error("Введите хотя бы одно ключевое слово!")
        else:
            with st.spinner("Поиск каналов... Это может занять время (учтите квоту API)"):
                try:
                    youtube = build('youtube', 'v3', developerKey=api_key)
                    channels_data = []
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
                        while len(channels_data) < target:
                            query = queries[current_query_index].strip()
                            if not query:
                                current_query_index = (current_query_index + 1) % len(queries)
                                continue
                            st.write(f"🔍 Поиск по: '{query}' (найдено: {len(channels_data)})")
                            
                            next_page_token = None
                            page_count = 0
                            while next_page_token is not None or page_count == 0:
                                if len(channels_data) >= target:
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
                                        if len(channels_data) >= target:
                                            break
                                        channel_id = item['snippet']['channelId']
                                        channel_details = get_channel_details(channel_id)
                                        if channel_details and channel_details['subscribers'] >= min_subscribers:
                                            if max_subscribers > 0 and channel_details['subscribers'] > max_subscribers:
                                                continue  # Пропускаем, если превышает максимум
                                            if channel_details['title'].lower() not in existing_titles:
                                                channels_data.append(channel_details)
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

                    # Сохранение с проверкой дубликатов
                    if channels_data:
                        added_count = 0
                        duplicates_count = 0
                        for ch in channels_data:
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
                        df_new = pd.DataFrame(channels_data)
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
                    else:
                        st.warning("⚠️ Каналы не найдены. Попробуйте другие ключевые слова или уменьшите мин. подписчиков.")

                except Exception as e:
                    st.error(f"Общая ошибка: {e}")

with tab2:
    st.header("📋 Сохранённые каналы")
    if st.button("Обновить данные", key="refresh_button"):
        st.rerun()  # Принудительная перезагрузка страницы
    
    existing_channels = load_channels()
    if existing_channels:
        df = pd.DataFrame(existing_channels)
        
        # Редактируемая таблица с чекбоксом для "viewed"
        st.subheader("Таблица сохранённых каналов")
        edited_df = st.data_editor(
            df,
            column_config={
                "viewed": st.column_config.CheckboxColumn(
                    "Просмотрено",
                    default=False,
                    required=False
                )
            },
            use_container_width=True,
            num_rows="dynamic"
        )
        
        # Сохранение изменений
        if st.button("Сохранить изменения", key="save_viewed"):
            # Обновляем JSON на основе edited_df
            updated_channels = edited_df.to_dict('records')
            save_channels(updated_channels)
            st.success("✅ Изменения сохранены!")
            st.rerun()  # Перезагружаем страницу для обновления
        
        # Статистика
        viewed_count = df['viewed'].sum() if 'viewed' in df.columns else 0
        total_count = len(df)
        st.metric("Всего каналов", total_count)
        st.metric("Просмотрено", viewed_count)
        
        # Скачивание полного CSV
        csv_full = df.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Скачать все CSV",
            data=csv_full,
            file_name=f'all_youtube_channels_{total_count}.csv',
            mime='text/csv'
        )
    else:
        st.info("📭 Пока нет сохранённых каналов. Запустите поиск в первой вкладке!")

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