# vim: set fileencoding=utf-8
import copy
import random
from typing import Any, Dict, List, Optional, Tuple

from bemani.backend.base import Status
from bemani.backend.jubeat.base import JubeatBase
from bemani.backend.jubeat.common import (
    JubeatDemodataGetHitchartHandler,
    JubeatDemodataGetNewsHandler,
    JubeatGamendRegisterHandler,
    JubeatGametopGetMeetingHandler,
    JubeatLobbyCheckHandler,
    JubeatLoggerReportHandler,
)
from bemani.backend.jubeat.stubs import JubeatKnit
from bemani.common import ValidatedDict, VersionConstants, Time
from bemani.data import Data, Score, UserID
from bemani.protocol import Node


class JubeatKnitAppend(
    JubeatDemodataGetHitchartHandler,
    JubeatDemodataGetNewsHandler,
    JubeatGamendRegisterHandler,
    JubeatGametopGetMeetingHandler,
    JubeatLobbyCheckHandler,
    JubeatLoggerReportHandler,
    JubeatBase,
):

    name = 'Jubeat Knit Append'
    version = VersionConstants.JUBEAT_KNIT_APPEND

    GAME_CHART_TYPE_BASIC = 0
    GAME_CHART_TYPE_ADVANCED = 1
    GAME_CHART_TYPE_EXTREME = 2

    def previous_version(self) -> Optional[JubeatBase]:
        return JubeatKnitAppend(self.data, self.config, self.model)

    def game_to_db_chart(self, game_chart: int, hard_mode: bool) -> int:
        if hard_mode:
            return {
                self.GAME_CHART_TYPE_BASIC: self.CHART_TYPE_HARD_BASIC,
                self.GAME_CHART_TYPE_ADVANCED: self.CHART_TYPE_HARD_ADVANCED,
                self.GAME_CHART_TYPE_EXTREME: self.CHART_TYPE_HARD_EXTREME,
            }[game_chart]
        else:
            return {
                self.GAME_CHART_TYPE_BASIC: self.CHART_TYPE_BASIC,
                self.GAME_CHART_TYPE_ADVANCED: self.CHART_TYPE_ADVANCED,
                self.GAME_CHART_TYPE_EXTREME: self.CHART_TYPE_EXTREME,
            }[game_chart]

    def db_to_game_chart(self, db_chart: int) -> int:
        return {
            self.CHART_TYPE_BASIC: self.GAME_CHART_TYPE_BASIC,
            self.CHART_TYPE_ADVANCED: self.GAME_CHART_TYPE_ADVANCED,
            self.CHART_TYPE_EXTREME: self.GAME_CHART_TYPE_EXTREME,
            self.CHART_TYPE_HARD_BASIC: self.GAME_CHART_TYPE_BASIC,
            self.CHART_TYPE_HARD_ADVANCED: self.GAME_CHART_TYPE_ADVANCED,
            self.CHART_TYPE_HARD_EXTREME: self.GAME_CHART_TYPE_EXTREME,
        }[db_chart]

    @classmethod
    def run_scheduled_work(cls, data: Data, config: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Insert daily FC challenges into the DB.
        """
        events = []
        if data.local.network.should_schedule(cls.game, cls.version, 'fc_challenge', 'daily'):
            # Generate a new list of two FC challenge songs.
            start_time, end_time = data.local.network.get_schedule_duration('daily')
            all_songs = set(song.id for song in data.local.music.get_all_songs(cls.game, cls.version))
            today_song = random.sample(all_songs, 1)[0]
            data.local.game.put_time_sensitive_settings(
                cls.game,
                cls.version,
                'fc_challenge',
                {
                    'start_time': start_time,
                    'end_time': end_time,
                    'today': today_song,
                },
            )
            events.append((
                'jubeat_fc_challenge_charts',
                {
                    'version': cls.version,
                    'today': today_song,
                },
            ))

            # Mark that we did some actual work here.
            data.local.network.mark_scheduled(cls.game, cls.version, 'fc_challenge', 'daily')
              
        return events

    def handle_shopinfo_regist_request(self, request: Node) -> Node:
        # Update the name of this cab for admin purposes
        self.update_machine_name(request.child_value('shop/name'))

        shopinfo = Node.void('shopinfo')
        data = Node.void('data')
        shopinfo.add_child(data)
        data.add_child(Node.u32('cabid', 1))
        data.add_child(Node.string('locationid', 'easerver'))
        data.add_child(Node.u8('is_send', 1))

        data.add_child(Node.s32_array(
            'white_music_list',
            [
                -1, -1, -1, -1,
                -1, -1, -1, -1,
                -1, -1, -1, -1,
                -1, -1, -1, -1,
                -16385, -1, -1,
                -1, -1, -1, -1,
                -1, -1, -1, -1,
                -1, -1, -1, -1,
                -1,
            ],
        ))
        data.add_child(Node.u8('tax_phase', 3))
        return shopinfo

    def handle_gametop_regist_request(self, request: Node) -> Node:
        data = request.child('data')
        player = data.child('player')
        passnode = player.child('pass')
        refid = passnode.child_value('refid')
        name = player.child_value('name')
        root = self.new_profile_by_refid(refid, name)
        return root
        
    def handle_gametop_get_pdata_request(self, request: Node) -> Node:
        data = request.child('data')
        player = data.child('player')
        passnode = player.child('pass')
        refid = passnode.child_value('refid')
        root = self.get_profile_by_refid(refid)
        if root is None:
            root = Node.void('gametop') 
            root.set_attribute('status', str(Status.NO_PROFILE))   
                    
        return root    
       
    def handle_gametop_get_mdata_request(self, request: Node) -> Node:
        data = request.child('data')
        player = data.child('player')
        playdata = Node.void('playdata')
        extid = player.child_value('jid')
        mdata_ver = player.child_value('mdata_ver')  # Game requests mdata 3 times per profile for some reason
        root = self.get_scores_by_extid(extid)
        if root is None:
            root = Node.void('gametop')
            root.set_attribute('status', str(Status.NO_PROFILE))                         
        return root       
        
        if mdata_ver != 1:
            root = Node.void('gametop')
            gametop = Node.void('gametop')
            gametop.set_attribute('method', 'get_mdata')
            gametop.add_child(Node.s32('retry', 0))
            data = Node.void('data')
            gametop.add_child(data)
            player = Node.void('player')
            data.add_child(player)
            player.add_child(Node.s32('jid', extid))
            player.add_child(Node.s8('mdata_ver', 3))        
            
        return root                 

    def handle_gametop_get_rival_mdata_request(self, request: Node) -> Node:
        data = request.child('data')
        player = data.child('player')
        extid = player.child_value('rival')
        
        return root


    def format_profile(self, userid: UserID, profile: ValidatedDict) -> Node:
        gametop = Node.void('gametop')
        root = Node.void('gametop')
        data = Node.void('data')
        root.add_child(data)
        player = Node.void('player')
        data.add_child(player)

        # Player info and statistics
        info = Node.void('info')
        player.add_child(info)
        info.add_child(Node.s16('jubility', profile.get_int('jubility')))
        info.add_child(Node.s16('jubility_yday', profile.get_int('jubility_yday')))
        info.add_child(Node.s8('acv_prog', profile.get_int('acv_prog')))
        info.add_child(Node.s8('acv_wool', profile.get_int('acv_wool')))
        info.add_child(Node.s8_array('acv_route_prog', [0, 0, 0, 0]))
        info.add_child(Node.s32('tune_cnt', profile.get_int('tune_cnt')))
        info.add_child(Node.s32('save_cnt', profile.get_int('save_cnt')))
        info.add_child(Node.s32('saved_cnt', profile.get_int('saved_cnt')))
        info.add_child(Node.s32('fc_cnt', profile.get_int('fc_cnt')))
        info.add_child(Node.s32('fc_seq_cnt', profile.get_int('fc_seq_cnt')))
        info.add_child(Node.s32('exc_cnt', profile.get_int('exc_cnt')))
        info.add_child(Node.s32('exc_seq_cnt', profile.get_int('exc_seq_cnt')))
        info.add_child(Node.s32('match_cnt', profile.get_int('match_cnt')))
        info.add_child(Node.s32('beat_cnt', profile.get_int('beat_cnt')))
        info.add_child(Node.s32('con_sel_cnt', profile.get_int('con_sel_cnt')))
        info.add_child(Node.s32('tag_cnt', profile.get_int('tag_cnt')))
        info.add_child(Node.s8('con_suggest_id', profile.get_int('acv_wool')))
        info.add_child(Node.s32('mynews_cnt', profile.get_int('mynews_cnt')))

        # Looks to be set to true when there's an old profile, stops tutorial from
        # happening on first load.
        info.add_child(Node.bool('inherit', profile.get_bool('inherit')))

        # Not saved, but loaded
        info.add_child(Node.s32('mtg_entry_cnt', 0))
        info.add_child(Node.s32('mtg_hold_cnt', 0))
        info.add_child(Node.u8('mtg_result', 0))

        # Secret unlocks
        item = Node.void('item')
        player.add_child(item)
        item.add_child(Node.s32_array('secret_list', [-1, -1]))
        item.add_child(Node.s16('theme_list', -1))
        item.add_child(Node.s32_array('marker_list', [-1, -1]))
        item.add_child(Node.s32_array('title_list', [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]))
        item.add_child(Node.s32_array('secret_new', [-1, -1]))
        item.add_child(Node.s16('theme_new', -1))
        item.add_child(Node.s32_array('marker_new', [-1, -1]))
        item.add_child(Node.s32_array('title_new', [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]))
        item.add_child(Node.s32_array('parts_list', [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]))

        new = Node.void('new')
        item.add_child(new)
        new.add_child(Node.s32_array('secret_list', [1, 1]))
        new.add_child(Node.s16('theme_list', -1))
        new.add_child(Node.s32_array('marker_list', [-1, -1]))
        new.add_child(Node.s32_array('title_list', [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]))

        # Last played data, for showing cursor and such
        lastdict = profile.get_dict('last')
        last = Node.void('last')
        player.add_child(last)
        last.add_child(Node.s32('music_id', lastdict.get_int('music_id')))
        last.add_child(Node.s8('marker', lastdict.get_int('marker')))
        last.add_child(Node.s16('title', lastdict.get_int('title')))
        last.add_child(Node.s8('theme', lastdict.get_int('theme')))
        last.add_child(Node.s8('sort', lastdict.get_int('sort')))
        last.add_child(Node.s8('rank_sort', lastdict.get_int('rank_sort')))
        last.add_child(Node.s8('combo_disp', lastdict.get_int('combo_disp')))
        last.add_child(Node.s8('seq_id', lastdict.get_int('seq_id')))
        last.add_child(Node.s8('msel_stat', lastdict.get_int('msel_stat')))
        last.add_child(Node.s16('parts', lastdict.get_int('parts')))
        last.add_child(Node.s8('category', lastdict.get_int('category')))
        last.add_child(Node.s64('play_time', lastdict.get_int('play_time')))
        last.add_child(Node.string('shopname', lastdict.get_str('shopname')))
        last.add_child(Node.string('areaname', lastdict.get_str('areaname')))

        # Miscelaneous crap
        player.add_child(Node.s32('session_id', 1))

        # Maybe hook this up? Unsure what it does, is it like IIDX dailies?
        today_music = Node.void('today_music')
        player.add_child(today_music)
        today_music.add_child(Node.s32('music_id', 0))

        # No news, ever.
        news = Node.void('news')
        player.add_child(news)
        news.add_child(Node.s16('checked', 0))

        # Add rivals to profile.
        rivallist = Node.void('rivallist')
        player.add_child(rivallist)

        links = self.data.local.user.get_links(self.game, self.version, userid)
        rivalcount = 0
        for link in links:
            if link.type != 'rival':
                continue

            rprofile = self.get_profile(link.other_userid)
            if rprofile is None:
                continue

            rival = Node.void('rival')
            rivallist.add_child(rival)
            rival.add_child(Node.s32('jid', rprofile.get_int('extid')))
            rival.add_child(Node.string('name', rprofile.get_str('name')))

            # Lazy way of keeping track of rivals, since we can only have 4
            # or the game with throw up. At least, I think Fulfill can have
            # 4 instead of the 3 found in newer versions, given the size of
            # the array that it loads the values in. However, to keep things
            # simple, I only supported three here.
            rivalcount += 1
            if rivalcount >= 3:
                break

        rivallist.set_attribute('count', str(rivalcount))

        # Unclear what this is. Looks related to Jubeat lab.
        mylist = Node.void('mylist')
        player.add_child(mylist)
        mylist.set_attribute('count', '0')       
        # No collaboration support yet.
        
        collabo = Node.void('collabo')
        player.add_child(collabo)
        collabo.add_child(Node.bool('success', False))
        collabo.add_child(Node.bool('completed', False))       

        # Daily FC challenge.
        entry = self.data.local.game.get_time_sensitive_settings(self.game, self.version, 'fc_challenge')
        if entry is None:
            entry = ValidatedDict()

        # Figure out if we've played these songs
        start_time, end_time = self.data.local.network.get_schedule_duration('daily')
        today_attempts = self.data.local.music.get_all_attempts(self.game, self.version, userid, entry.get_int('today', -1), timelimit=start_time)
        
        challenge = Node.void('challenge')
        player.add_child(challenge)
        today = Node.void('today')
        challenge.add_child(today)
        today.add_child(Node.s32('music_id', 0))    
        
        onlynow = Node.void('onlynow')
        challenge.add_child(onlynow)
        onlynow.add_child(Node.s32('magic_no', 0))
        onlynow.add_child(Node.s16('cycle', 0))      
        # Basic profile info
        player.add_child(Node.string('name', profile.get_str('name', 'なし')))
        player.add_child(Node.s32('jid', profile.get_int('extid')))
        player.add_child(Node.string('refid', profile.get_str('refid')))
        
        history = Node.void('history')
        data.add_child(history)
        history.set_attribute('count', '0')  
        
        return root       


    def unformat_profile(self, userid: UserID, request: Node, oldprofile: ValidatedDict) -> ValidatedDict:
        newprofile = copy.deepcopy(oldprofile)
        data = request.child('data')

        # Grab player information
        player = data.child('player')

        # Grab last information. Lots of this will be filled in while grabbing scores
        last = newprofile.get_dict('last')
        last.replace_int('play_time', player.child_value('time_gameend'))
        last.replace_str('shopname', player.child_value('shopname'))
        last.replace_str('areaname', player.child_value('areaname'))

        # Grab player info for echoing back
        info = player.child('info')
        if info is not None:
            newprofile.replace_int('jubility', info.child_value('jubility'))
            newprofile.replace_int('jubility_yday', info.child_value('jubility_yday'))
            newprofile.replace_int('acv_prog', info.child_value('acv_prog'))
            newprofile.replace_int('acv_point', info.child_value('acv_point'))
            newprofile.replace_int('acv_wool', info.child_value('acv_wool'))
            newprofile.replace_int('acv_route_prog', info.child_value('acv_route_prog'))                    
            newprofile.replace_int('tune_cnt', info.child_value('tune_cnt'))
            newprofile.replace_int('save_cnt', info.child_value('save_cnt'))
            newprofile.replace_int('saved_cnt', info.child_value('saved_cnt'))
            newprofile.replace_int('fc_cnt', info.child_value('fc_cnt'))
            newprofile.replace_int('fc_seq_cnt', info.child_value('fc_seq_cnt'))
            newprofile.replace_int('exc_cnt', info.child_value('exc_cnt'))
            newprofile.replace_int('exc_seq_cnt', info.child_value('exc_seq_cnt'))          
            newprofile.replace_int('match_cnt', info.child_value('match_cnt'))
            newprofile.replace_int('beat_cnt', info.child_value('beat_cnt'))
            newprofile.replace_int('con_sel_cnt', info.child_value('con_sel_cnt'))
            newprofile.replace_int('tag_cnt', info.child_value('tag_cnt'))
            newprofile.replace_int('con_suggest_id', info.child_value('con_suggest_id'))
            newprofile.replace_int('mynews_cnt', info.child_value('mynews_cnt'))

        # Grab unlock progress
        item = player.child('item')
        if item is not None:
            newprofile.replace_int_array('secret_list', 2, item.child_value('secret_list'))
            newprofile.replace_int_array('title_list', 24, item.child_value('title_list'))
            newprofile.replace_int('theme_list', item.child_value('theme_list'))
            newprofile.replace_int_array('marker_list', 2, item.child_value('marker_list'))
            newprofile.replace_int_array('parts_list', 96, item.child_value('parts_list'))
            newprofile.replace_int_array('secret_list_new', 2, item.child_value('secret_new'))
            newprofile.replace_int_array('title_list_new', 24, item.child_value('title_new'))
            newprofile.replace_int('theme_list_new', item.child_value('theme_new'))
            newprofile.replace_int_array('marker_list_new', 2, item.child_value('marker_new'))

        # Grab bistro progress
        bistro = player.child('bistro')
        if bistro is not None:
            newprofile.replace_int('bistro_carry_over', bistro.child_value('carry_over'))

            chefdata = newprofile.get_dict('chef')
            chef = bistro.child('chef')
            if chef is not None:
                chefdata.replace_int('id', chef.child_value('id'))
                chefdata.replace_int('ability', chef.child_value('ability'))
                chefdata.replace_int('remain', chef.child_value('remain'))
                chefdata.replace_int('rate', chef.child_value('rate'))
            newprofile.replace_dict('chef', chefdata)

            for route in bistro.children:
                if route.name != 'route':
                    continue

                gourmates = route.child('gourmates')
                routeid = gourmates.child_value('id')
                satisfaction = gourmates.child_value('satisfaction_s32')
                self.data.local.user.put_achievement(
                    self.game,
                    self.version,
                    userid,
                    routeid,
                    'route',
                    {
                        'satisfaction': satisfaction,
                    },
                )

        # Get timestamps for played songs
        timestamps: Dict[int, int] = {}
        history = player.child('history')
        if history is not None:
            for tune in history.children:
                if tune.name != 'tune':
                    continue
                entry = int(tune.attribute('log_id'))
                ts = int(tune.child_value('timestamp') / 1000)
                timestamps[entry] = ts

        # Grab scores and save those
        result = data.child('result')
        if result is not None:
            for tune in result.children:
                if tune.name != 'tune':
                    continue
                result = tune.child('player')

                last.replace_int('marker', tune.child_value('marker'))
                last.replace_int('title', tune.child_value('title'))
                last.replace_int('parts', tune.child_value('parts'))
                last.replace_int('theme', tune.child_value('theme'))
                last.replace_int('sort', tune.child_value('sort'))
                last.replace_int('category', tune.child_value('category'))
                last.replace_int('rank_sort', tune.child_value('rank_sort'))
                last.replace_int('combo_disp', tune.child_value('combo_disp'))

                songid = tune.child_value('music')
                entry = int(tune.attribute('id'))
                timestamp = timestamps.get(entry, Time.now())
                chart = self.game_to_db_chart(int(result.child('score').attribute('seq')), bool(result.child_value('is_hard_mode')))
                points = result.child_value('score')
                flags = int(result.child('score').attribute('clear'))
                combo = int(result.child('score').attribute('combo'))
                ghost = result.child_value('mbar')

                # Miscelaneous last data for echoing to profile get
                last.replace_int('music_id', songid)
                last.replace_int('seq_id', int(result.child('score').attribute('seq')))

                mapping = {
                    self.GAME_FLAG_BIT_CLEARED: self.PLAY_MEDAL_CLEARED,
                    self.GAME_FLAG_BIT_FULL_COMBO: self.PLAY_MEDAL_FULL_COMBO,
                    self.GAME_FLAG_BIT_EXCELLENT: self.PLAY_MEDAL_EXCELLENT,
                    self.GAME_FLAG_BIT_NEARLY_FULL_COMBO: self.PLAY_MEDAL_NEARLY_FULL_COMBO,
                    self.GAME_FLAG_BIT_NEARLY_EXCELLENT: self.PLAY_MEDAL_NEARLY_EXCELLENT,
                }

                # Figure out the highest medal based on bits passed in
                medal = self.PLAY_MEDAL_FAILED
                for bit in mapping:
                    if flags & bit > 0:
                        medal = max(medal, mapping[bit])

                self.update_score(userid, timestamp, songid, chart, points, medal, combo, ghost)

        # Save back last information gleaned from results
        newprofile.replace_dict('last', last)

        # Keep track of play statistics
        self.update_play_statistics(userid)

        return newprofile

    def format_scores(self, userid: UserID, profile: ValidatedDict, scores: List[Score]) -> Node:
        scores = self.data.remote.music.get_scores(self.game, self.version, userid)

        root = Node.void('gametop')
        datanode = Node.void('data')
        root.add_child(datanode)
        player = Node.void('player')
        datanode.add_child(player)
        player.add_child(Node.s32('jid', profile.get_int('extid')))
        playdata = Node.void('playdata')
        player.add_child(playdata)
        playdata.set_attribute('count', str(len(scores)))
       
        music = ValidatedDict()
        for score in scores:
            chart = self.db_to_game_chart(score.chart)
            data = music.get_dict(str(score.id))
            play_cnt = data.get_int_array('play_cnt', 3)
            clear_cnt = data.get_int_array('clear_cnt', 3)
            clear_flags = data.get_int_array('clear_flags', 3)
            fc_cnt = data.get_int_array('fc_cnt', 3)
            ex_cnt = data.get_int_array('ex_cnt', 3)
            points = data.get_int_array('points', 3)

            # This means that we already assigned a value and it was greater than current
            # This is possible because we iterate through both hard mode and normal mode scores
            # and treat them equally.
            # TODO: generalize score merging code into a library since this does not account for
            # having a full combo in hard mode but not in normal.
            if points[chart] >= score.points:
                continue
            # Replace data for this chart type
            play_cnt[chart] = score.plays
            clear_cnt[chart] = score.data.get_int('clear_count')
            fc_cnt[chart] = score.data.get_int('full_combo_count')
            ex_cnt[chart] = score.data.get_int('excellent_count')
            points[chart] = score.points

            # Format the clear flags
            clear_flags[chart] = self.GAME_FLAG_BIT_PLAYED
            if score.data.get_int('clear_count') > 0:
                clear_flags[chart] |= self.GAME_FLAG_BIT_CLEARED
            if score.data.get_int('full_combo_count') > 0:
                clear_flags[chart] |= self.GAME_FLAG_BIT_FULL_COMBO
            if score.data.get_int('excellent_count') > 0:
                clear_flags[chart] |= self.GAME_FLAG_BIT_EXCELLENT

            # Save chart data back
            data.replace_int_array('play_cnt', 3, play_cnt)
            data.replace_int_array('clear_cnt', 3, clear_cnt)
            data.replace_int_array('clear_flags', 3, clear_flags)
            data.replace_int_array('fc_cnt', 3, fc_cnt)
            data.replace_int_array('ex_cnt', 3, ex_cnt)
            data.replace_int_array('points', 3, points)

            # Update the ghost (untyped)
            ghost = data.get('ghost', [None, None, None])
            ghost[chart] = score.data.get('ghost')
            data['ghost'] = ghost

            # Save it back
            music.replace_dict(str(score.id), data)

        for scoreid in music:
            scoredata = music[scoreid]
            musicdata = Node.void('musicdata')
            playdata.add_child(musicdata)

            musicdata.set_attribute('music_id', scoreid)
            musicdata.add_child(Node.s32_array('play_cnt', scoredata.get_int_array('play_cnt', 3)))
            musicdata.add_child(Node.s32_array('clear_cnt', scoredata.get_int_array('clear_cnt', 3)))
            musicdata.add_child(Node.s32_array('fc_cnt', scoredata.get_int_array('fc_cnt', 3)))
            musicdata.add_child(Node.s32_array('ex_cnt', scoredata.get_int_array('ex_cnt', 3)))
            musicdata.add_child(Node.s32_array('score', scoredata.get_int_array('points', 3)))
            musicdata.add_child(Node.s8_array('clear', scoredata.get_int_array('clear_flags', 3)))

            ghosts = scoredata.get('ghost', [None, None, None])
            for i in range(len(ghosts)):
                ghost = ghosts[i]
                if ghost is None:
                    continue

                bar = Node.u8_array('bar', ghost)
                musicdata.add_child(bar)
                bar.set_attribute('seq', str(i))

        return root
