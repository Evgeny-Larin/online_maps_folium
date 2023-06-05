import folium
from folium import plugins
import pandas as pd
import streamlit as st


#заменяет полное название компании на сокращенное
def replacer(x):
    #словарь замен
    replace_dict = {'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ': 'ООО',
                    'ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО': 'ПАО',
                    'ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО': 'ОАО',
                    'АКЦИОНЕРНОЕ ОБЩЕСТВО': 'АО'}
    for old, new in replace_dict.items():
        x = x.upper().replace(old, new)
    return x

#определяет Топ13 компаний
#принимает df с точками внутри региона (например, p_kem)
def points_rating(x):
    #выделим ТОП-12 по количеству наиболее крупных сетей, остальные сохраним в Прочие
    #посчитаем количество точек в той или иной сети
    points_count = x.groupby('name', as_index = False)\
                    .agg({'lat':'count'})\
                    .sort_values('lat', ascending = False)

    #назначим ранги для каждой сети, где 1 - самая крупная
    points_count['rank'] = points_count['lat'].rank(method = 'first', ascending = False)

    #сохраним отдельно ТОП-12 сетей
    top12 = points_count[(points_count['rank']<=12)].drop(columns = ['rank'])
    
    #сохраним отдельно прочие
    other_points = points_count[(points_count['rank']>12)].drop(columns = ['name'])
    #создадим столбец "Прочие"
    other_points['name'] = 'ПРОЧИЕ'
    #найдём суммарное количество точек всех прочих сетей
    other_points = other_points.groupby('name', as_index = False)\
                               .agg({'lat':'sum'})
    
    #добавляем прочих к топ-12
    top13 = pd.concat([top12, other_points])
   
    #создаем столбец для легенды
    top13['labels'] = top13['name'] + " — " + top13['lat'].astype('str')

    #переименовываем столбец с количеством точек
    top13.rename(columns = {'lat':'all_count'}, inplace = True)
    return top13

#принимает df с топ13 компаний и установленную пользователем hex палитру
#присваивает каждой компании соответсвующий цвет, возвращает словарь {компания:цвет}
def color_distributor(top13, hex_palette):
    #берём название всех компаний в топе
    companies = top13.name.tolist()
    #удаляем ПРОЧИЕ
    try:
        companies.remove('ПРОЧИЕ')
    except:
        pass
    #присваиваем компаниям цвета из палитры
    comp_n_colors = {}
    x = 0
    for i in companies:
        comp_n_colors[i] = [hex_palette[x]]
        x += 1    
        
    return comp_n_colors

#генератор карты
#принимает df с координатами точек в столбцах lat и lon
def map_creator(df):
    russia_map = folium.Map(location = [df.lat.median(), df.lon.median()], #начальная позиция камеры
                            zoom_start = 7, #начальный зум камеры
                            tiles = 'cartodbpositron') #стиль карты
    #добавляем плагины
    #полноэкранный режим
    plugins.Fullscreen(
    position="bottomleft",
    force_separate_button=True).add_to(russia_map)
    #поиск
    plugins.Geocoder(collapsed=True, position='topleft').add_to(russia_map)
    #миникарта
    minimap = plugins.MiniMap()
    russia_map.add_child(minimap)
    return russia_map

#добавляет города на карту
#принимает df с базой городов и карту, на которую нужно добавить города
def city_creator(city_db, russia_map):
    return city_db.apply(lambda row:folium.Circle(location=[row["Latitude"], row["Longitude"]], #координаты города
                                                    radius=(row["Population"]/60 if row["Population"]/50>6000 else 6000), #радиус окружности
                                                    tooltip=row['CityName'], #всплывающая подсказка
                                                    fill=True, #настройка заполнения цветом
                                                    weight=1,  #настройка прозрачности и т.д.
                                                    fill_opacity=0.02).add_to(russia_map), axis=1)

#добавляет точки на карту
#принимает df с координатами необходимых точек, карту, на которую нужно добавить города, палитру цветов
def points_creator(points, russia_map, hex_palette):
    #определяем топ13 компаний и прочие
    top13 = points_rating(points)
    #добавляем к основному df признак топовости компании, остальных помечаем как Прочие
    points_region = pd.merge(points,
                             top13,
                             how = 'left',
                             on = 'name')\
                      .sort_values('all_count', ascending = False)

    try:
        points_region['labels'].fillna(top13[top13['name'] == 'ПРОЧИЕ']['labels'][0], inplace = True)
    except:
        pass
    
    #распределяем цвета из hex палитры среди топ13 компаний
    comp_n_colors = color_distributor(top13, hex_palette)

    #группируем по подписи легенды
    for grp_name, df_grp in points_region.groupby(['labels'], sort = False):
        #берём соответсвующее имя компании
        name = df_grp['name'].unique()[0]
        try:
            #получаем цвет компании
            color = comp_n_colors[name][0]
        except:
            #если цвет не нашли - цвет серый
            color = 'grey'
        #объединяем в группы, устанавливаем цвет и название группы 
        feature_group = folium.FeatureGroup(f'<span style="color: {color};"> ⬤ {grp_name}</span>')
        #для каждой строки в группе
        for row in df_grp.itertuples():
            #рисуем точку. row3 и row4 - координаты, row2 - адрес точки
            folium.Circle(location=[row[3], row[4]], 
                                         radius=90,
                                         popup=repr(row[2]),
                                         tooltip=row[1], 
                                         fill = True, 
                                         weight=0.5, 
                                         color = 'black', 
                                         weight_color = 'black', 
                                         fill_opacity=1, 
                                         fill_color=color).add_to(feature_group)
        feature_group.add_to(russia_map)

    #добавляем панель управления группами (легенду) на карту
    folium.map.LayerControl('topright', collapsed= False).add_to(russia_map)