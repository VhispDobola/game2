"""
TITANFALL-STYLE FPS GAME
========================
A first-person shooter with advanced movement mechanics including wall running,
grappling hooks, double jumping, and sliding. Features wave-based combat,
boss battles, loot system, inventory management, and a shop system.

ORGANIZATION:
1. Imports and Setup
2. Class Definitions
3. Game Data Structures
4. Audio System
5. Environment Setup
6. Player Setup
7. UI Elements
8. Game Systems (Movement, Combat, Boss, Enemy, Loot)
9. Input Handling
10. Main Game Loop
11. Game Start
"""

# =============================================================================
# 1. IMPORTS AND SETUP
# =============================================================================
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import os, random
from ursina.shaders import basic_lighting_shader
from perlin_noise import PerlinNoise
from math import cos, sin, radians

# Initialize Ursina
app = Ursina()

# =============================================================================
# 2. CLASS DEFINITIONS
# =============================================================================

class Inventory:
    """Player inventory system for managing items"""
    def __init__(self, max_size=20):
        self.items = []
        self.max_size = max_size
        self.equipped_weapon = None
        self.equipped_armor = None
    
    def add_item(self, item):
        if len(self.items) < self.max_size:
            self.items.append(item)
            return True
        return False
    
    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
            return True
        return False
    
    def get_items_by_type(self, item_type):
        return [item for item in self.items if item['type'] == item_type]
    
    def sort_items(self, sort_by='rarity'):
        if sort_by == 'rarity':
            rarity_order = {'common': 0, 'uncommon': 1, 'rare': 2, 'legendary': 3}
            self.items.sort(key=lambda x: rarity_order.get(x.get('rarity', 'common'), 0))
        elif sort_by == 'type':
            self.items.sort(key=lambda x: x.get('type', ''))
        elif sort_by == 'name':
            self.items.sort(key=lambda x: x.get('name', ''))

class Bullet(Entity):
    """Projectile class for weapons"""
    def __init__(self, position, direction, weapon_type='pistol'):
        weapon_data = weapons[weapon_type]
        super().__init__(
            parent=scene,
            model='sphere',
            color=weapon_data['color'],
            scale=weapon_data['bullet_size'],
            position=position,
            collider='sphere'
        )
        self.direction = direction.normalized()
        self.speed = weapon_data['bullet_speed']
        self.damage = weapon_data['damage']
        self.lifetime = 2
        self.timer = 0

    def update(self):
        self.position += self.direction * self.speed * time.dt
        self.timer += time.dt
        
        if self.timer >= self.lifetime or (self.position - player.position).length() > 100:
            if self in bullets:
                bullets.remove(self)
            destroy(self)

class BossAttackIndicator(Entity):
    """Visual indicator for boss attacks"""
    def __init__(self, position, attack_type, delay=2.0):
        super().__init__(
            model='sphere',
            color=color.red,
            scale=(3, 0.1, 3),
            position=position,
            alpha=0.7
        )
        self.attack_type = attack_type
        self.delay = delay
        self.timer = 0
        self.original_scale = self.scale
        self.pulse_speed = 2
        
    def update(self):
        self.timer += time.dt
        pulse = (sin(self.timer * self.pulse_speed) + 1) * 0.3 + 0.7
        self.scale = self.original_scale * pulse
        
        if self.timer > self.delay * 0.7:
            self.color = color.red
        elif self.timer > self.delay * 0.4:
            self.color = color.orange
        else:
            self.color = color.yellow
            
        if self.timer >= self.delay:
            if self in boss_attack_indicators:
                boss_attack_indicators.remove(self)
            destroy(self)

# =============================================================================
# 3. GAME DATA STRUCTURES
# =============================================================================

# Weapons configuration
weapons = {
    'pistol': {
        'name': 'Pistol',
        'cost': 0,
        'damage': 25,
        'fire_rate': 0.5,
        'ammo_capacity': 12,
        'reload_time': 2.0,
        'description': 'Basic sidearm. Reliable and accurate.',
        'model': 'pistol',
        'color': color.gray,
        'bullet_size': 0.1,
        'bullet_speed': 50
    },
    'assault_rifle': {
        'name': 'Assault Rifle',
        'cost': 500,
        'damage': 35,
        'fire_rate': 0.1,
        'ammo_capacity': 30,
        'reload_time': 2.5,
        'description': 'High rate of fire. Good for crowd control.',
        'model': 'assault_rifle',
        'color': color.dark_gray,
        'bullet_size': 0.08,
        'bullet_speed': 60
    },
    'laser': {
        'name': 'Laser Rifle',
        'cost': 800,
        'damage': 50,
        'fire_rate': 0.3,
        'ammo_capacity': 20,
        'reload_time': 3.0,
        'description': 'High damage energy weapon. Pierces enemies.',
        'model': 'laser',
        'color': color.cyan,
        'bullet_size': 0.06,
        'bullet_speed': 80
    }
}

# Armor configuration
armors = {
    'light': {
        'name': 'Light Armor',
        'cost': 300,
        'protection': 0.8,
        'description': 'Lightweight protection. Minimal movement penalty.',
        'color': color.light_gray
    },
    'medium': {
        'name': 'Medium Armor',
        'cost': 600,
        'protection': 0.6,
        'description': 'Balanced protection and mobility.',
        'color': color.gray
    },
    'heavy': {
        'name': 'Heavy Armor',
        'cost': 1000,
        'protection': 0.4,
        'description': 'Maximum protection. Slower movement.',
        'color': color.dark_gray
    }
}

# Perks configuration
perks = {
    'health_boost': {
        'name': 'Health Boost',
        'description': 'Increase max health by 25',
        'effect': 'health_boost'
    },
    'speed_boost': {
        'name': 'Speed Boost',
        'description': 'Increase movement speed by 20%',
        'effect': 'speed_boost'
    },
    'damage_boost': {
        'name': 'Damage Boost',
        'description': 'Increase weapon damage by 25%',
        'effect': 'damage_boost'
    },
    'ammo_capacity': {
        'name': 'Ammo Capacity',
        'description': 'Increase ammo capacity by 50%',
        'effect': 'ammo_capacity'
    },
    'reload_speed': {
        'name': 'Reload Speed',
        'description': 'Decrease reload time by 30%',
        'effect': 'reload_speed'
    },
    'double_jump_enhanced': {
        'name': 'Enhanced Double Jump',
        'description': 'Double jump now has 3 charges',
        'effect': 'double_jump_enhanced'
    },
    'grapple_range': {
        'name': 'Extended Grapple',
        'description': 'Increase grapple range by 50%',
        'effect': 'grapple_range'
    },
    'wall_run_duration': {
        'name': 'Wall Run Master',
        'description': 'Increase wall run duration by 100%',
        'effect': 'wall_run_duration'
    },
    'health_regen': {
        'name': 'Health Regeneration',
        'description': 'Slowly regenerate health over time',
        'effect': 'health_regen'
    },
    'armor_piercing': {
        'name': 'Armor Piercing',
        'description': 'Bullets ignore enemy armor',
        'effect': 'armor_piercing'
    },
    'explosive_rounds': {
        'name': 'Explosive Rounds',
        'description': 'Bullets explode on impact',
        'effect': 'explosive_rounds'
    },
    'ricochet': {
        'name': 'Ricochet',
        'description': 'Bullets bounce off surfaces',
        'effect': 'ricochet'
    }
}

# Loot items configuration
loot_items = {
    'health_potion': {
        'name': 'Health Potion',
        'type': 'consumable',
        'rarity': 'common',
        'description': 'Restore 50 health points',
        'effect': 'heal_50',
        'color': color.red,
        'model': 'sphere'
    },
    'ammo_pack': {
        'name': 'Ammo Pack',
        'type': 'consumable',
        'rarity': 'common',
        'description': 'Refill all ammo',
        'effect': 'refill_ammo',
        'color': color.yellow,
        'model': 'cube'
    },
    'speed_boost': {
        'name': 'Speed Boost',
        'type': 'consumable',
        'rarity': 'uncommon',
        'description': 'Temporary speed boost for 30 seconds',
        'effect': 'speed_boost_temp',
        'color': color.cyan,
        'model': 'sphere'
    },
    'damage_boost': {
        'name': 'Damage Boost',
        'type': 'consumable',
        'rarity': 'uncommon',
        'description': 'Temporary damage boost for 30 seconds',
        'effect': 'damage_boost_temp',
        'color': color.orange,
        'model': 'sphere'
    },
    'rare_weapon': {
        'name': 'Rare Weapon',
        'type': 'weapon',
        'rarity': 'rare',
        'description': 'Random rare weapon',
        'effect': 'random_rare_weapon',
        'color': color.magenta,
        'model': 'cube'
    },
    'legendary_weapon': {
        'name': 'Legendary Weapon',
        'type': 'weapon',
        'rarity': 'legendary',
        'description': 'Random legendary weapon',
        'effect': 'random_legendary_weapon',
        'color': color.gold,
        'model': 'sphere'
    },
    'armor_piece': {
        'name': 'Armor Piece',
        'type': 'armor',
        'rarity': 'uncommon',
        'description': 'Random armor piece',
        'effect': 'random_armor',
        'color': color.blue,
        'model': 'cube'
    },
    'money_bag': {
        'name': 'Money Bag',
        'type': 'currency',
        'rarity': 'common',
        'description': 'Contains 100-500 money',
        'effect': 'random_money',
        'color': color.green,
        'model': 'cube'
    }
}

# =============================================================================
# 4. AUDIO SYSTEM
# =============================================================================

def load_audio_safe(path, loop=False, autoplay=False):
    """Safely load audio files with multiple path attempts"""
    possible_paths = [
        path,
        os.path.join(os.getcwd(), path),
        os.path.join(os.path.dirname(__file__), path),
        os.path.join('assets', path),
        os.path.join('sounds', path),
    ]
    
    for try_path in possible_paths:
        if os.path.exists(try_path):
            print(f'[SUCCESS] Loaded audio file: {try_path}')
            try:
                return Audio(try_path, loop=loop, autoplay=autoplay)
            except Exception as e:
                print(f'[ERROR] Failed to load audio {try_path}: {e}')
                continue
    
    print(f'[WARNING] No audio file found for: {path}')
    return None

# Load audio files
print("=== LOADING AUDIO FILES ===")
shoot_sfx = load_audio_safe('assets/reload.wav')  # Use reload sound as fallback for shoot
reload_sfx = load_audio_safe('assets/reload.wav')
laser_sfx = load_audio_safe('assets/laser.wav')
laser_reload_sfx = load_audio_safe('assets/laserreload.wav')
hit_sfx = load_audio_safe('assets/reload.wav')  # Use reload sound as fallback for hit
explosion_sfx = load_audio_safe('assets/reload.wav')  # Use reload sound as fallback for explosion
pickup_sfx = load_audio_safe('assets/reload.wav')  # Use reload sound as fallback for pickup
background_music = load_audio_safe('assets/mixkit-vertigo-597.mp3', loop=True, autoplay=True)
print("=== AUDIO LOADING COMPLETE ===")

# =============================================================================
# 5. GLOBAL VARIABLES
# =============================================================================

# Game state variables
player = None
gun = None
enemies = []
bosses = []
bullets = []
powerups = []
boss_attack_indicators = []
enemy_kills = 0
wave = 1
enemies_per_wave = 5
game_over = False
shop_open = False
debug_mode = False
inventory_open = False
loot_items_world = []

# Game state management
game_state = 'home'  # 'home', 'playing', 'perk_selection', 'game_over'
selected_perks = []
current_armor = None
perk_choices = []

# =============================================================================
# 6. ENVIRONMENT SETUP
# =============================================================================

# Sky and lighting
Sky()
DirectionalLight().look_at(Vec3(1, -1, -1))

# Procedural terrain
terrain_size = 300
terrain_res = 100
noise = PerlinNoise(octaves=4, seed=random.randint(0,10000))
verts = []
uvs = []
tris = []

for z in range(terrain_res):
    for x in range(terrain_res):
        y = noise([x/terrain_res*3, z/terrain_res*3]) * 3
        verts.append((x - terrain_res//2, y, z - terrain_res//2))
        uvs.append((x/terrain_res, z/terrain_res))

for z in range(terrain_res-1):
    for x in range(terrain_res-1):
        i = x + z*terrain_res
        tris += [i, i+1, i+terrain_res, i+1, i+terrain_res+1, i+terrain_res]

terrain = Entity(
    model=Mesh(vertices=verts, triangles=tris, uvs=uvs, mode='triangle'),
    color=color.green,
    collider='box',
    scale=(terrain_size/(terrain_res-1),1,terrain_size/(terrain_res-1)),
    shader=basic_lighting_shader
)

# Backup ground plane
ground_plane = Entity(
    model='plane',
    color=color.green,
    scale=(300, 1, 300),
    position=(0, -2, 0),
    collider='box'
)

# Obstacles and cover
for _ in range(50):
    size = random.uniform(2, 8)
    Entity(model='cube', color=color.gray, scale=(size, size * 2, size), 
           position=(random.uniform(-140, 140), size, random.uniform(-140, 140)), collider='box')

# Boundary walls
wall_height = 10
wall_thickness = 2
Entity(model='cube', color=color.dark_gray, scale=(300, wall_height, wall_thickness), position=(0, wall_height/2, 150), collider='box')
Entity(model='cube', color=color.dark_gray, scale=(300, wall_height, wall_thickness), position=(0, wall_height/2, -150), collider='box')
Entity(model='cube', color=color.dark_gray, scale=(wall_thickness, wall_height, 300), position=(150, wall_height/2, 0), collider='box')
Entity(model='cube', color=color.dark_gray, scale=(wall_thickness, wall_height, 300), position=(-150, wall_height/2, 0), collider='box')

# Wall running walls
wall_run_walls = []

# Central arena walls
arena_wall_height = 30
arena_wall_length = 80
arena_wall_thickness = 3

# North wall
north_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_length, arena_wall_height, arena_wall_thickness), 
    position=(0, arena_wall_height/2, 60), 
    collider='box'
)
wall_run_walls.append(north_wall)

# South wall
south_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_length, arena_wall_height, arena_wall_thickness), 
    position=(0, arena_wall_height/2, -60), 
    collider='box'
)
wall_run_walls.append(south_wall)

# East wall
east_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_thickness, arena_wall_height, arena_wall_length), 
    position=(60, arena_wall_height/2, 0), 
    collider='box'
)
wall_run_walls.append(east_wall)

# West wall
west_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_thickness, arena_wall_height, arena_wall_length), 
    position=(-60, arena_wall_height/2, 0), 
    collider='box'
)
wall_run_walls.append(west_wall)

# Corner walls
corner_wall_height = 25
corner_wall_length = 40

corner_walls = [
    Entity(model='cube', color=color.dark_gray, scale=(corner_wall_length, corner_wall_height, 2), position=(40, corner_wall_height/2, 40), collider='box'),
    Entity(model='cube', color=color.dark_gray, scale=(2, corner_wall_height, corner_wall_length), position=(40, corner_wall_height/2, 40), collider='box'),
    Entity(model='cube', color=color.dark_gray, scale=(corner_wall_length, corner_wall_height, 2), position=(-40, corner_wall_height/2, 40), collider='box'),
    Entity(model='cube', color=color.dark_gray, scale=(2, corner_wall_height, corner_wall_length), position=(-40, corner_wall_height/2, 40), collider='box'),
    Entity(model='cube', color=color.dark_gray, scale=(corner_wall_length, corner_wall_height, 2), position=(40, corner_wall_height/2, -40), collider='box'),
    Entity(model='cube', color=color.dark_gray, scale=(2, corner_wall_height, corner_wall_length), position=(40, corner_wall_height/2, -40), collider='box'),
    Entity(model='cube', color=color.dark_gray, scale=(corner_wall_length, corner_wall_height, 2), position=(-40, corner_wall_height/2, -40), collider='box'),
    Entity(model='cube', color=color.dark_gray, scale=(2, corner_wall_height, corner_wall_length), position=(-40, corner_wall_height/2, -40), collider='box'),
]

wall_run_walls.extend(corner_walls)

# Floating platforms
platform_positions = [
    (20, 15, 20), (20, 15, -20), (-20, 15, 20), (-20, 15, -20),
    (0, 25, 30), (0, 25, -30), (30, 25, 0), (-30, 25, 0),
    (15, 35, 15), (15, 35, -15), (-15, 35, 15), (-15, 35, -15)
]

for pos in platform_positions:
    platform = Entity(
        model='cube',
        color=color.light_gray,
        scale=(8, 1, 8),
        position=pos,
        collider='box'
    )
    wall_run_walls.append(platform)

# =============================================================================
# 7. PLAYER SETUP
# =============================================================================

# Initialize player
player = FirstPersonController()
player.gravity = 0.8
player.jump_height = 2
player.cursor.visible = False
player.speed = 7.5
player.health = 100
player.max_health = 100
player.ammo = 10
player.max_ammo = 10
player.score = 0
player.reload_time = 1.5
player.is_reloading = False
player.is_aiming = False
player.is_sliding = False
player.slide_speed = 12
player.slide_timer = 0
player.slide_duration = 1.0
player.money = 1000
player.current_weapon = 'pistol'
player.inventory = Inventory()  # Now Inventory class is defined before this line

# Titanfall 2 Movement System
player.is_wall_running = False
player.wall_run_timer = 0
player.wall_run_duration = 2.0
player.wall_run_speed = 12
player.wall_normal = Vec3(0, 0, 0)
player.wall_run_direction = Vec3(0, 0, 0)

# Grappling hook system
player.grapple_hook = None
player.is_grappling = False
player.grapple_target = None
player.grapple_speed = 25
player.grapple_range = 50
player.grapple_cooldown = 0
player.grapple_cooldown_time = 1.0

# Double jump system
player.has_double_jump = True
player.double_jump_available = True
player.jump_count = 0

# Wall detection
player.wall_detection_range = 3.0
player.wall_run_angle_threshold = 30

# =============================================================================
# 8. UI ELEMENTS
# =============================================================================

# HUD Elements
health_bar = Text(text='Health: 100', position=(-0.85, 0.45), scale=1.5)
ammo_bar = Text(text='Ammo: 10/10', position=(-0.85, 0.38), scale=1.5)
score_text = Text(text='Score: 0', position=(-0.85, 0.31), scale=1.5)
wave_text = Text(text='Wave: 1', position=(-0.85, 0.24), scale=1.5)
money_text = Text(text='Money: $1000', position=(-0.85, 0.17), scale=1.5)
weapon_text = Text(text='Weapon: Pistol', position=(-0.85, 0.10), scale=1.5)
game_over_text = Text(text='', origin=(0,0), scale=3, color=color.red)
shop_text = Text(text='Press B for Shop', position=(0.7, 0.45), scale=1.2, color=color.yellow)
inventory_text = Text(text='Press I for Inventory', position=(0.7, 0.52), scale=1.2, color=color.cyan)

# Movement HUD
movement_text = Text(text='', position=(0.7, 0.38), scale=1.0, color=color.cyan)
grapple_cooldown_text = Text(text='', position=(0.7, 0.31), scale=1.0, color=color.orange)
wall_run_text = Text(text='', position=(0.7, 0.24), scale=1.0, color=color.green)

# Instructions
instructions_text = Text(
    text='Movement: WASD=Move, SPACE=Jump/Double Jump, E=Grapple to Cursor, W+Wall=Wall Run, SHIFT=Slide\nMouse=Look Around (M=Toggle Mouse Lock), F3=Debug Mode, K=Show All Controls, I=Inventory', 
    position=(-0.85, -0.4), 
    scale=0.8, 
    color=color.light_gray
)

# Crosshair
crosshair_h = Entity(parent=camera.ui, model='quad', scale=(0.015, 0.002), color=color.white, position=(0, 0, 0.5))
crosshair_v = Entity(parent=camera.ui, model='quad', scale=(0.002, 0.015), color=color.white, position=(0, 0, 0.5))
crosshair_dot = Entity(parent=camera.ui, model='sphere', scale=0.003, color=color.red, position=(0, 0, 0.6))

# Gun model
gun = Entity(parent=camera.ui, position=(0.5, -0.25, 1.2), scale=0.25)

# Shop UI
shop_panel = Panel(scale=(0.5,0.6), color=color.rgba(30,30,30,220), enabled=False)
shop_title = Text('ARMORY', parent=shop_panel, y=0.25, scale=2, color=color.yellow, origin=(0,0))
shop_desc = Text('Press 1: Pistol (Free)\nPress 2: Assault Rifle ($500)\nPress 3: Laser Rifle ($800)\nESC to close', parent=shop_panel, y=0.1, scale=1.2, origin=(0,0))
shop_money = Text('', parent=shop_panel, y=-0.18, scale=1.2, origin=(0,0))

# Inventory UI
inventory_panel = Panel(scale=(0.7,0.8), color=color.rgba(20,20,20,240), enabled=False)
inventory_title = Text('INVENTORY', parent=inventory_panel, y=0.35, scale=2.5, color=color.cyan, origin=(0,0))
inventory_info = Text('', parent=inventory_panel, y=0.25, scale=1.0, color=color.white, origin=(0,0))
inventory_items = Text('', parent=inventory_panel, y=0.1, scale=0.8, color=color.white, origin=(0,0))
inventory_controls = Text('ESC to close | 1-9 to use items | S to sort', parent=inventory_panel, y=-0.35, scale=1.0, color=color.yellow, origin=(0,0))

# Pause Menu
pause_panel = Panel(scale=(0.4,0.3), color=color.rgba(20,20,20,230), enabled=False)
pause_text = Text('PAUSED', parent=pause_panel, y=0.1, scale=2, color=color.white, origin=(0,0))
resume_btn = Button(text='Resume', parent=pause_panel, y=-0.05, scale=(0.3,0.1))
quit_btn = Button(text='Quit', parent=pause_panel, y=-0.15, scale=(0.3,0.1))

# Keybind Display
keybind_panel = Panel(scale=(0.6,0.8), color=color.rgba(20,20,20,230), enabled=False)
keybind_title = Text('CONTROLS', parent=keybind_panel, y=0.35, scale=2, color=color.yellow, origin=(0,0))

# Movement Controls
movement_title = Text('MOVEMENT', parent=keybind_panel, y=0.25, scale=1.5, color=color.cyan, origin=(0,0))
movement_controls = Text(
    'WASD - Move\nSPACE - Jump/Double Jump\nSHIFT - Slide (when on ground)\nW + Wall - Wall Run\nE - Grapple to Cursor\nMouse - Look Around\nM - Toggle Mouse Lock',
    parent=keybind_panel, y=0.1, scale=0.8, color=color.white, origin=(0,0)
)

# Combat Controls
combat_title = Text('COMBAT', parent=keybind_panel, y=-0.05, scale=1.5, color=color.red, origin=(0,0))
combat_controls = Text(
    'Left Mouse - Shoot\nRight Mouse - Aim Down Sights\nR - Reload',
    parent=keybind_panel, y=-0.2, scale=0.8, color=color.white, origin=(0,0)
)

# Menu Controls
menu_title = Text('MENU', parent=keybind_panel, y=-0.35, scale=1.5, color=color.green, origin=(0,0))
menu_controls = Text(
    'B - Open Shop\nI - Open Inventory\nESC - Pause/Close Shop\nF3 - Debug Mode\nK - Show Controls\nQ - Quit Game',
    parent=keybind_panel, y=-0.5, scale=0.8, color=color.white, origin=(0,0)
)

# Shop Controls
shop_controls_text = Text(
    '1 - Buy Pistol (Free)\n2 - Buy Assault Rifle ($500)\n3 - Buy Laser Rifle ($800)',
    parent=keybind_panel, y=-0.65, scale=0.8, color=color.yellow, origin=(0,0)
)

# Inventory Controls
inventory_controls_text = Text(
    '1-9 - Use Items\nS - Sort by Rarity',
    parent=keybind_panel, y=-0.8, scale=0.8, color=color.cyan, origin=(0,0)
)
