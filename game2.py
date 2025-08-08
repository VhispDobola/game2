from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import os, random
from ursina.shaders import basic_lighting_shader
from perlin_noise import PerlinNoise
from math import cos, sin, radians

app = Ursina()
# window.icon = None  # Commented out to avoid TypeError

# === Safe Audio Loader ===
def load_audio_safe(path, loop=False, autoplay=False):
    # Try multiple possible paths
    possible_paths = [
        path,  # Direct path
        os.path.join(os.getcwd(), path),  # Current directory
        os.path.join(os.path.dirname(__file__), path),  # Same directory as script
        os.path.join('assets', path),  # Assets folder
        os.path.join('sounds', path),  # Sounds folder
    ]
    
    for try_path in possible_paths:
        if os.path.exists(try_path):
            print(f'[SUCCESS] Loaded audio file: {try_path}')
            try:
                return Audio(try_path, loop=loop, autoplay=autoplay)
            except Exception as e:
                print(f'[ERROR] Failed to load audio {try_path}: {e}')
                continue
    
    # If no file found, create a silent audio placeholder
    print(f'[WARNING] No audio file found for: {path}')
    print(f'[INFO] Tried paths: {possible_paths}')
    print(f'[INFO] Current working directory: {os.getcwd()}')
    print(f'[INFO] Script directory: {os.path.dirname(__file__)}')
    
    # Create a silent audio placeholder to prevent crashes
    return None

# === Sounds ===
print("=== LOADING AUDIO FILES ===")
shoot_sfx = load_audio_safe('assets/shoot.wav')
reload_sfx = load_audio_safe('assets/reload.wav')
laser_sfx = load_audio_safe('assets/laser.wav')
laser_reload_sfx = load_audio_safe('assets/laserreload.wav')
hit_sfx = load_audio_safe('hit.wav')
explosion_sfx = load_audio_safe('explosion.wav')
pickup_sfx = load_audio_safe('pickup.wav')
background_music = load_audio_safe('assets/mixkit-vertigo-597.mp3', loop=True, autoplay=True)
print("=== AUDIO LOADING COMPLETE ===")

# === Global Variables ===
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
debug_mode = False  # Debug mode for movement testing

# === New Game State Variables ===
game_state = 'home'  # 'home', 'playing', 'perk_selection', 'game_over'
selected_perks = []
current_armor = None
perk_choices = []

# === Environment ===
Sky()

# --- Procedural Bumpy Terrain ---
terrain_size = 300
terrain_res = 100
noise = PerlinNoise(octaves=4, seed=random.randint(0,10000))
verts = []
uvs = []
tris = []
for z in range(terrain_res):
    for x in range(terrain_res):
        y = noise([x/terrain_res*3, z/terrain_res*3]) * 3  # Reduced from 8 to 3 for smoother terrain
        verts.append((x - terrain_res//2, y, z - terrain_res//2))
        uvs.append((x/terrain_res, z/terrain_res))
for z in range(terrain_res-1):
    for x in range(terrain_res-1):
        i = x + z*terrain_res
        tris += [i, i+1, i+terrain_res, i+1, i+terrain_res+1, i+terrain_res]
terrain = Entity(
    model=Mesh(vertices=verts, triangles=tris, uvs=uvs, mode='triangle'),
    texture='grass',
    collider='box',  # Changed from 'mesh' to 'box' for better collision detection
    scale=(terrain_size/(terrain_res-1),1,terrain_size/(terrain_res-1)),
    shader=basic_lighting_shader
)

# Add a flat ground plane as backup to prevent falling through
ground_plane = Entity(
    model='plane',
    color=color.green,
    scale=(300, 1, 300),
    position=(0, -2, 0),  # Slightly below terrain
    collider='box',
    texture='grass'
)

DirectionalLight().look_at(Vec3(1, -1, -1))

# Add obstacles and cover
for _ in range(50):
    size = random.uniform(2, 8)
    Entity(model='cube', color=color.gray, scale=(size, size * 2, size), 
           position=(random.uniform(-140, 140), size, random.uniform(-140, 140)), collider='box')

# Add boundary walls to prevent falling off
wall_height = 10
wall_thickness = 2
Entity(model='cube', color=color.dark_gray, scale=(300, wall_height, wall_thickness), position=(0, wall_height/2, 150), collider='box')
Entity(model='cube', color=color.dark_gray, scale=(300, wall_height, wall_thickness), position=(0, wall_height/2, -150), collider='box')
Entity(model='cube', color=color.dark_gray, scale=(wall_thickness, wall_height, 300), position=(150, wall_height/2, 0), collider='box')
Entity(model='cube', color=color.dark_gray, scale=(wall_thickness, wall_height, 300), position=(-150, wall_height/2, 0), collider='box')

# === Large Walls for Wall Running and Grappling ===
# Create massive walls for Titanfall-style movement
wall_run_walls = []

# Central arena walls (tall and wide for wall running)
arena_wall_height = 30
arena_wall_length = 80
arena_wall_thickness = 3

# North wall
north_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_length, arena_wall_height, arena_wall_thickness), 
    position=(0, arena_wall_height/2, 60), 
    collider='box',
    texture='white_cube'
)
wall_run_walls.append(north_wall)

# South wall
south_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_length, arena_wall_height, arena_wall_thickness), 
    position=(0, arena_wall_height/2, -60), 
    collider='box',
    texture='white_cube'
)
wall_run_walls.append(south_wall)

# East wall
east_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_thickness, arena_wall_height, arena_wall_length), 
    position=(60, arena_wall_height/2, 0), 
    collider='box',
    texture='white_cube'
)
wall_run_walls.append(east_wall)

# West wall
west_wall = Entity(
    model='cube', 
    color=color.gray, 
    scale=(arena_wall_thickness, arena_wall_height, arena_wall_length), 
    position=(-60, arena_wall_height/2, 0), 
    collider='box',
    texture='white_cube'
)
wall_run_walls.append(west_wall)

# Corner walls for complex wall running routes
corner_wall_height = 25
corner_wall_length = 40

# Corner walls
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

# Floating platforms for advanced movement
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

# === Player ===
player = FirstPersonController()
player.gravity = 0.8  # Increased gravity to prevent getting stuck on slopes
player.jump_height = 2
player.cursor.visible = False  # Disable cursor for FPS controls
player.speed = 7.5  # Increased by 150%
player.health = 100
player.max_health = 100
player.ammo = 10
player.max_ammo = 10
player.score = 0
player.reload_time = 1.5
player.is_reloading = False
player.is_aiming = False
player.is_sliding = False
player.slide_speed = 12  # Faster than normal speed
player.slide_timer = 0
player.slide_duration = 1.0  # Slide for 1 second
player.money = 1000  # Starting money for shop
player.current_weapon = 'pistol'
player.inventory = Inventory()  # Add inventory to player

# === Titanfall 2 Movement System ===
# Wall running and grappling mechanics
player.is_wall_running = False
player.wall_run_timer = 0
player.wall_run_duration = 2.0  # Max wall run time
player.wall_run_speed = 12  # Faster than normal speed
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

# Wall detection - simplified
player.wall_detection_range = 3.0  # Increased range for easier detection
player.wall_run_angle_threshold = 30  # Reduced angle threshold for easier wall running

# === HUD ===
health_bar = Text(text='Health: 100', position=(-0.85, 0.45), scale=1.5)
ammo_bar = Text(text='Ammo: 10/10', position=(-0.85, 0.38), scale=1.5)
score_text = Text(text='Score: 0', position=(-0.85, 0.31), scale=1.5)
wave_text = Text(text='Wave: 1', position=(-0.85, 0.24), scale=1.5)
money_text = Text(text='Money: $1000', position=(-0.85, 0.17), scale=1.5)
weapon_text = Text(text='Weapon: Pistol', position=(-0.85, 0.10), scale=1.5)
game_over_text = Text(text='', origin=(0,0), scale=3, color=color.red)
shop_text = Text(text='Press B for Shop', position=(0.7, 0.45), scale=1.2, color=color.yellow)
inventory_text = Text(text='Press I for Inventory', position=(0.7, 0.52), scale=1.2, color=color.cyan)

# === Movement HUD ===
movement_text = Text(text='', position=(0.7, 0.38), scale=1.0, color=color.cyan)
grapple_cooldown_text = Text(text='', position=(0.7, 0.31), scale=1.0, color=color.orange)
wall_run_text = Text(text='', position=(0.7, 0.24), scale=1.0, color=color.green)

# === Movement Instructions ===
instructions_text = Text(
    text='Movement: WASD=Move, SPACE=Jump/Double Jump, E=Grapple to Cursor, W+Wall=Wall Run, SHIFT=Slide\nMouse=Look Around (M=Toggle Mouse Lock), F3=Debug Mode, K=Show All Controls, I=Inventory', 
    position=(-0.85, -0.4), 
    scale=0.8, 
    color=color.light_gray
)

# === Crosshair ===
# Create a small cross crosshair
crosshair_h = Entity(parent=camera.ui, model='quad', texture='white_cube', scale=(0.015, 0.002), color=color.white, position=(0, 0, 0.5))
crosshair_v = Entity(parent=camera.ui, model='quad', texture='white_cube', scale=(0.002, 0.015), color=color.white, position=(0, 0, 0.5))
crosshair_dot = Entity(parent=camera.ui, model='sphere', scale=0.003, color=color.red, position=(0, 0, 0.6))

# === Game State ===
bullets = []
enemies = []
wave = 1
enemy_kills = 0
enemies_per_wave = 5
powerups = []
loot_items_world = []  # Track loot items in the world
game_over = False
shop_open = False
debug_mode = False  # Debug mode for movement testing

# === Weapons Data ===
weapons = {
    'pistol': {
        'name': 'Pistol',
        'cost': 0,
        'damage': 25,
        'fire_rate': 0.5,
        'ammo_capacity': 12,
        'reload_time': 2.0,
        'description': 'Basic sidearm. Reliable and accurate.',
        'model': 'pistol'
    },
    'assault_rifle': {
        'name': 'Assault Rifle',
        'cost': 500,
        'damage': 35,
        'fire_rate': 0.1,
        'ammo_capacity': 30,
        'reload_time': 2.5,
        'description': 'High rate of fire. Good for crowd control.',
        'model': 'assault_rifle'
    },
    'laser': {
        'name': 'Laser Rifle',
        'cost': 800,
        'damage': 50,
        'fire_rate': 0.3,
        'ammo_capacity': 20,
        'reload_time': 3.0,
        'description': 'High damage energy weapon. Pierces enemies.',
        'model': 'laser'
    }
}

# === Armor Data ===
armors = {
    'light': {
        'name': 'Light Armor',
        'cost': 300,
        'protection': 0.8,  # 20% damage reduction
        'description': 'Lightweight protection. Minimal movement penalty.',
        'color': color.light_gray
    },
    'medium': {
        'name': 'Medium Armor',
        'cost': 600,
        'protection': 0.6,  # 40% damage reduction
        'description': 'Balanced protection and mobility.',
        'color': color.gray
    },
    'heavy': {
        'name': 'Heavy Armor',
        'cost': 1000,
        'protection': 0.4,  # 60% damage reduction
        'description': 'Maximum protection. Slower movement.',
        'color': color.dark_gray
    }
}

# === Perks Data ===
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

# === Loot Items Data ===
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
        'color': color.purple,
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

# === Inventory System ===
class Inventory:
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

# === Loot Drop System ===
def drop_loot(position, enemy_type='normal', is_boss=False):
    """Drop loot at the specified position based on enemy type"""
    dropped_items = []
    
    if is_boss:
        # Bosses always drop loot
        num_drops = random.randint(2, 4)  # 2-4 items
        for _ in range(num_drops):
            # Higher chance for rare/legendary items
            rarity_roll = random.random()
            if rarity_roll < 0.1:  # 10% legendary
                possible_items = [item for item in loot_items.values() if item['rarity'] == 'legendary']
            elif rarity_roll < 0.3:  # 20% rare
                possible_items = [item for item in loot_items.values() if item['rarity'] == 'rare']
            elif rarity_roll < 0.6:  # 30% uncommon
                possible_items = [item for item in loot_items.values() if item['rarity'] == 'uncommon']
            else:  # 40% common
                possible_items = [item for item in loot_items.values() if item['rarity'] == 'common']
            
            if possible_items:
                item_key = random.choice(list(possible_items))
                dropped_items.append(create_loot_entity(position, item_key))
    else:
        # Normal enemies have a chance to drop loot
        if random.random() < 0.15:  # 15% chance for normal enemies
            rarity_roll = random.random()
            if rarity_roll < 0.05:  # 5% rare
                possible_items = [item for item in loot_items.values() if item['rarity'] == 'rare']
            elif rarity_roll < 0.2:  # 15% uncommon
                possible_items = [item for item in loot_items.values() if item['rarity'] == 'uncommon']
            else:  # 80% common
                possible_items = [item for item in loot_items.values() if item['rarity'] == 'common']
            
            if possible_items:
                item_key = random.choice(list(possible_items))
                dropped_items.append(create_loot_entity(position, item_key))
    
    return dropped_items

def create_loot_entity(position, item_key):
    """Create a visual loot entity in the world"""
    item_data = loot_items[item_key]
    
    # Create the loot entity
    loot_entity = Entity(
        model=item_data['model'],
        color=item_data['color'],
        position=position + Vec3(0, 1, 0),  # Slightly above ground
        scale=0.5,
        collider='sphere'
    )
    
    # Add item data to entity
    loot_entity.item_data = item_data
    loot_entity.item_key = item_key
    
    # Add floating animation
    def float_animation():
        loot_entity.y += sin(time.time() * 2) * 0.1
        invoke(float_animation, delay=0.05)
    
    float_animation()
    
    # Add glow effect for rare items
    if item_data['rarity'] in ['rare', 'legendary']:
        glow = Entity(
            model='sphere',
            color=item_data['color'],
            position=loot_entity.position,
            scale=loot_entity.scale * 1.5,
            alpha=0.3
        )
        loot_entity.glow = glow
        
        def glow_animation():
            glow.alpha = 0.3 + sin(time.time() * 3) * 0.2
            invoke(glow_animation, delay=0.05)
        
        glow_animation()
    
    return loot_entity

def pickup_loot(loot_entity):
    """Pick up a loot item and add it to inventory"""
    if player.inventory.add_item(loot_entity.item_data):
        # Apply immediate effects for consumables
        if loot_entity.item_data['type'] == 'consumable':
            apply_consumable_effect(loot_entity.item_data)
        elif loot_entity.item_data['type'] == 'currency':
            apply_currency_effect(loot_entity.item_data)
        
        # Remove the loot entity
        if hasattr(loot_entity, 'glow'):
            destroy(loot_entity.glow)
        destroy(loot_entity)
        
        # Play pickup sound
        if pickup_sfx:
            pickup_sfx.play()
        
        return True
    return False

def apply_consumable_effect(item_data):
    """Apply the effect of a consumable item"""
    effect = item_data['effect']
    
    if effect == 'heal_50':
        player.health = min(player.max_health, player.health + 50)
        print(f"Used {item_data['name']}: +50 Health")
    elif effect == 'refill_ammo':
        player.ammo = player.max_ammo
        print(f"Used {item_data['name']}: Ammo Refilled")
    elif effect == 'speed_boost_temp':
        # Temporary speed boost
        original_speed = player.speed
        player.speed *= 1.5
        print(f"Used {item_data['name']}: Speed Boost for 30 seconds")
        
        def restore_speed():
            player.speed = original_speed
            print("Speed boost expired")
        
        invoke(restore_speed, delay=30)
    elif effect == 'damage_boost_temp':
        # Temporary damage boost (would need to be implemented in weapon system)
        print(f"Used {item_data['name']}: Damage Boost for 30 seconds")

def apply_currency_effect(item_data):
    """Apply the effect of a currency item"""
    if item_data['effect'] == 'random_money':
        money_amount = random.randint(100, 500)
        player.money += money_amount
        print(f"Found {item_data['name']}: +${money_amount}")

# === Custom Model Creation Functions ===
def create_pistol_model():
    """Create a detailed pistol model"""
    gun = Entity(model=None)
    
    # Main barrel
    Entity(parent=gun, model='cube', color=color.dark_gray, scale=(0.05, 0.05, 0.4), position=(0, 0, 0.15))
    # Barrel tip
    Entity(parent=gun, model='sphere', color=color.black, scale=(0.06, 0.06, 0.06), position=(0, 0, 0.35))
    # Grip
    Entity(parent=gun, model='cube', color=color.brown, scale=(0.08, 0.2, 0.05), position=(0, -0.12, -0.05))
    # Trigger guard
    Entity(parent=gun, model='cube', color=color.black, scale=(0.05, 0.05, 0.08), position=(0, -0.05, 0.05))
    # Trigger
    Entity(parent=gun, model='cube', color=color.gold, scale=(0.02, 0.03, 0.02), position=(0, -0.08, 0.05))
    # Slide
    Entity(parent=gun, model='cube', color=color.light_gray, scale=(0.06, 0.04, 0.3), position=(0, 0.02, 0.1))
    # Sights
    Entity(parent=gun, model='cube', color=color.black, scale=(0.02, 0.02, 0.02), position=(0, 0.04, 0.25))
    Entity(parent=gun, model='cube', color=color.black, scale=(0.02, 0.02, 0.02), position=(0, 0.04, -0.05))
    
    return gun

def create_assault_rifle_model():
    """Create a detailed assault rifle model"""
    gun = Entity(model=None)
    
    # Main body
    Entity(parent=gun, model='cube', color=color.dark_gray, scale=(0.08, 0.08, 0.6), position=(0, 0, 0.2))
    # Barrel
    Entity(parent=gun, model='cylinder', color=color.black, scale=(0.04, 0.04, 0.3), position=(0, 0, 0.5))
    # Stock
    Entity(parent=gun, model='cube', color=color.brown, scale=(0.06, 0.1, 0.2), position=(0, 0, -0.1))
    # Grip
    Entity(parent=gun, model='cube', color=color.dark_gray, scale=(0.06, 0.15, 0.05), position=(0, -0.12, 0.1))
    # Magazine
    Entity(parent=gun, model='cube', color=color.black, scale=(0.04, 0.12, 0.04), position=(0, -0.18, 0.15))
    # Scope
    Entity(parent=gun, model='cylinder', color=color.black, scale=(0.03, 0.03, 0.08), position=(0, 0.06, 0.2))
    # Muzzle flash suppressor
    Entity(parent=gun, model='cylinder', color=color.gray, scale=(0.05, 0.05, 0.05), position=(0, 0, 0.65))
    
    return gun

def create_laser_rifle_model():
    """Create a futuristic laser rifle model"""
    gun = Entity(model=None)
    
    # Main body
    Entity(parent=gun, model='cube', color=color.dark_blue, scale=(0.06, 0.06, 0.5), position=(0, 0, 0.15))
    # Energy core
    Entity(parent=gun, model='sphere', color=color.cyan, scale=(0.08, 0.08, 0.08), position=(0, 0, 0.1))
    # Laser barrel
    Entity(parent=gun, model='cylinder', color=color.red, scale=(0.03, 0.03, 0.4), position=(0, 0, 0.35))
    # Grip
    Entity(parent=gun, model='cube', color=color.dark_gray, scale=(0.05, 0.12, 0.04), position=(0, -0.1, 0.05))
    # Energy cells
    for i in range(3):
        Entity(parent=gun, model='sphere', color=color.yellow, scale=(0.02, 0.02, 0.02), 
               position=(0.03, 0, 0.1 + i * 0.05))
    # Holographic sight
    Entity(parent=gun, model='cube', color=color.cyan, scale=(0.04, 0.02, 0.04), position=(0, 0.04, 0.2))
    
    return gun

def create_grunt_model():
    """Create a grunt enemy model"""
    enemy = Entity(model=None)
    
    # Body
    Entity(parent=enemy, model='cube', color=color.orange, scale=(0.8, 1.2, 0.6), position=(0, 1, 0))
    # Head
    Entity(parent=enemy, model='sphere', color=color.orange, scale=(0.4, 0.4, 0.4), position=(0, 2, 0))
    # Eyes
    Entity(parent=enemy, model='sphere', color=color.red, scale=(0.05, 0.05, 0.05), position=(-0.1, 2.1, 0.3))
    Entity(parent=enemy, model='sphere', color=color.red, scale=(0.05, 0.05, 0.05), position=(0.1, 2.1, 0.3))
    # Arms
    Entity(parent=enemy, model='cube', color=color.orange, scale=(0.2, 0.8, 0.2), position=(-0.6, 1.2, 0))
    Entity(parent=enemy, model='cube', color=color.orange, scale=(0.2, 0.8, 0.2), position=(0.6, 1.2, 0))
    # Legs
    Entity(parent=enemy, model='cube', color=color.orange, scale=(0.2, 0.8, 0.2), position=(-0.2, 0.4, 0))
    Entity(parent=enemy, model='cube', color=color.orange, scale=(0.2, 0.8, 0.2), position=(0.2, 0.4, 0))
    
    return enemy

def create_brute_model():
    """Create a brute enemy model"""
    enemy = Entity(model=None)
    
    # Massive body
    Entity(parent=enemy, model='cube', color=color.red, scale=(1.2, 1.8, 0.8), position=(0, 1.5, 0))
    # Head
    Entity(parent=enemy, model='sphere', color=color.red, scale=(0.6, 0.6, 0.6), position=(0, 2.8, 0))
    # Horns
    Entity(parent=enemy, model='sphere', color=color.red, scale=(0.1, 0.2, 0.1), position=(-0.2, 3.1, 0))
    Entity(parent=enemy, model='sphere', color=color.red, scale=(0.1, 0.2, 0.1), position=(0.2, 3.1, 0))
    # Eyes
    Entity(parent=enemy, model='sphere', color=color.yellow, scale=(0.08, 0.08, 0.08), position=(-0.15, 2.9, 0.4))
    Entity(parent=enemy, model='sphere', color=color.yellow, scale=(0.08, 0.08, 0.08), position=(0.15, 2.9, 0.4))
    # Massive arms
    Entity(parent=enemy, model='cube', color=color.red, scale=(0.3, 1.2, 0.3), position=(-0.8, 1.8, 0))
    Entity(parent=enemy, model='cube', color=color.red, scale=(0.3, 1.2, 0.3), position=(0.8, 1.8, 0))
    # Legs
    Entity(parent=enemy, model='cube', color=color.red, scale=(0.3, 1.0, 0.3), position=(-0.3, 0.5, 0))
    Entity(parent=enemy, model='cube', color=color.red, scale=(0.3, 1.0, 0.3), position=(0.3, 0.5, 0))
    
    return enemy

def create_crawler_model():
    """Create a crawler enemy model"""
    enemy = Entity(model=None)
    
    # Low body
    Entity(parent=enemy, model='sphere', color=color.violet, scale=(1.2, 0.4, 0.8), position=(0, 0.4, 0))
    # Head
    Entity(parent=enemy, model='sphere', color=color.violet, scale=(0.3, 0.3, 0.3), position=(0, 0.8, 0.3))
    # Eyes
    Entity(parent=enemy, model='sphere', color=color.white, scale=(0.05, 0.05, 0.05), position=(-0.08, 0.85, 0.5))
    Entity(parent=enemy, model='sphere', color=color.white, scale=(0.05, 0.05, 0.05), position=(0.08, 0.85, 0.5))
    # Tentacles/legs
    for i in range(6):
        angle = i * 60
        x = cos(radians(angle)) * 0.6
        z = sin(radians(angle)) * 0.6
        Entity(parent=enemy, model='sphere', color=color.violet, scale=(0.1, 0.3, 0.1), 
               position=(x, 0.2, z))
    
    return enemy

def create_titan_boss_model():
    """Create a detailed titan boss model"""
    boss = Entity(model=None)
    
    # Massive armored body
    Entity(parent=boss, model='cube', color=color.dark_gray, scale=(2.5, 3, 1.5), position=(0, 2, 0))
    # Chest armor
    Entity(parent=boss, model='cube', color=color.gray, scale=(2, 1.5, 1.2), position=(0, 2.5, 0))
    # Shoulder armor
    Entity(parent=boss, model='cube', color=color.gray, scale=(0.8, 0.8, 0.8), position=(-1.5, 3, 0))
    Entity(parent=boss, model='cube', color=color.gray, scale=(0.8, 0.8, 0.8), position=(1.5, 3, 0))
    # Helmet
    Entity(parent=boss, model='sphere', color=color.dark_gray, scale=(0.8, 0.8, 0.8), position=(0, 4.5, 0))
    # Helmet visor
    Entity(parent=boss, model='cube', color=color.red, scale=(0.6, 0.2, 0.1), position=(0, 0, 4.5, 0.3))
    # Arms
    Entity(parent=boss, model='cube', color=color.dark_gray, scale=(0.4, 1.5, 0.4), position=(-1.8, 2.5, 0))
    Entity(parent=boss, model='cube', color=color.dark_gray, scale=(0.4, 1.5, 0.4), position=(1.8, 2.5, 0))
    # Legs
    Entity(parent=boss, model='cube', color=color.dark_gray, scale=(0.5, 1.8, 0.5), position=(-0.6, 0.9, 0))
    Entity(parent=boss, model='cube', color=color.dark_gray, scale=(0.5, 1.8, 0.5), position=(0.6, 0.9, 0))
    # Energy core
    Entity(parent=boss, model='sphere', color=color.blue, scale=(0.3, 0.3, 0.3), position=(0, 2, 0.5))
    
    return boss

def create_warlock_boss_model():
    """Create a detailed warlock boss model"""
    boss = Entity(model=None)
    
    # Main body
    Entity(parent=boss, model='sphere', color=color.purple, scale=(1.5, 2, 1.5), position=(0, 2, 0))
    # Robe
    Entity(parent=boss, model='sphere', color=color.dark_purple, scale=(2, 1.5, 2), position=(0, 1, 0))
    # Head
    Entity(parent=boss, model='sphere', color=color.purple, scale=(0.6, 0.6, 0.6), position=(0, 3.5, 0))
    # Eyes
    Entity(parent=boss, model='sphere', color=color.cyan, scale=(0.08, 0.08, 0.08), position=(-0.15, 3.6, 0.4))
    Entity(parent=boss, model='sphere', color=color.cyan, scale=(0.08, 0.08, 0.08), position=(0.15, 3.6, 0.4))
    # Staff
    Entity(parent=boss, model='cylinder', color=color.gold, scale=(0.05, 2, 0.05), position=(0.8, 1.5, 0))
    # Staff orb
    Entity(parent=boss, model='sphere', color=color.cyan, scale=(0.2, 0.2, 0.2), position=(0.8, 2.5, 0))
    # Floating orbs (will be animated)
    for i in range(4):
        orb = Entity(parent=boss, model='sphere', color=color.cyan, scale=0.3)
        orb.orbit_speed = 2 + i * 0.5
        orb.orbit_radius = 2
        orb.orbit_angle = i * 90
    
    return boss

def create_behemoth_boss_model():
    """Create a detailed behemoth boss model"""
    boss = Entity(model=None)
    
    # Massive body
    Entity(parent=boss, model='cube', color=color.brown, scale=(2.5, 2, 2), position=(0, 2, 0))
    # Head
    Entity(parent=boss, model='sphere', color=color.brown, scale=(1, 1, 1), position=(0, 3.5, 0.5))
    # Horns
    Entity(parent=boss, model='sphere', color=color.dark_brown, scale=(0.2, 0.8, 0.2), position=(-0.4, 4.2, 0.5))
    Entity(parent=boss, model='sphere', color=color.dark_brown, scale=(0.2, 0.8, 0.2), position=(0.4, 4.2, 0.5))
    # Eyes
    Entity(parent=boss, model='sphere', color=color.red, scale=(0.15, 0.15, 0.15), position=(-0.25, 3.7, 1.2))
    Entity(parent=boss, model='sphere', color=color.red, scale=(0.15, 0.15, 0.15), position=(0.25, 3.7, 1.2))
    # Snout
    Entity(parent=boss, model='sphere', color=color.dark_brown, scale=(0.4, 0.3, 0.6), position=(0, 3.2, 1.5))
    # Legs
    Entity(parent=boss, model='cube', color=color.brown, scale=(0.4, 1.5, 0.4), position=(-0.8, 0.75, 0))
    Entity(parent=boss, model='cube', color=color.brown, scale=(0.4, 1.5, 0.4), position=(0.8, 0.75, 0))
    Entity(parent=boss, model='cube', color=color.brown, scale=(0.4, 1.5, 0.4), position=(-0.8, 0.75, 0.8))
    Entity(parent=boss, model='cube', color=color.brown, scale=(0.4, 1.5, 0.4), position=(0.8, 0.75, 0.8))
    # Tail
    Entity(parent=boss, model='sphere', color=color.brown, scale=(0.3, 0.3, 1), position=(0, 1.5, -1.5))
    
    return boss

# === Titanfall 2 Movement Functions ===
def detect_wall_run():
    """Detect if player can wall run and return wall normal - Simplified version"""
    player_pos = player.position
    
    # Check all wall run walls using simple distance-based detection
    for wall in wall_run_walls:
        distance = (player_pos - wall.position).length()
        if distance < player.wall_detection_range:
            # Simple wall normal calculation - wall faces outward from center
            wall_to_center = (wall.position - Vec3(0, wall.position.y, 0)).normalized()
            wall_normal = wall_to_center
            
            # Check if player is close enough to wall and moving forward
            if held_keys['w'] and player.y > 0.5:
                return wall_normal, wall
    
    return None, None

def start_wall_run(wall_normal, wall):
    """Start wall running"""
    if not player.is_wall_running and player.y > 0.5:  # Must be off ground
        player.is_wall_running = True
        player.wall_run_timer = 0
        player.wall_normal = wall_normal
        player.wall_run_direction = wall_normal.cross(Vec3(0, 1, 0)).normalized()
        player.speed = player.wall_run_speed
        
        # Tilt camera for wall run effect
        camera.rotation_x = 15
        camera.rotation_z = 15
        
        # Create wall run particles
        for _ in range(5):
            particle = Entity(
                model='sphere',
                color=color.blue,
                scale=0.1,
                position=player.position + Vec3(random.uniform(-0.5, 0.5), 0, random.uniform(-0.5, 0.5))
            )
            particle.velocity = Vec3(random.uniform(-2, 2), random.uniform(1, 3), random.uniform(-2, 2))
            particle.lifetime = 1.0
            particle.timer = 0
            
            def update_particle(particle=particle):
                particle.timer += time.dt
                particle.position += particle.velocity * time.dt
                particle.scale *= 0.95
                if particle.timer >= particle.lifetime:
                    destroy(particle)
            
            # Store update function reference
            particle.update_func = update_particle

def end_wall_run():
    """End wall running"""
    if player.is_wall_running:
        player.is_wall_running = False
        player.speed = 7.5  # Return to normal speed
        camera.rotation_x = 0
        camera.rotation_z = 0

def grapple_to_target(target_pos):
    """Grapple to a target position"""
    if player.grapple_cooldown <= 0 and not player.is_grappling:
        player.is_grappling = True
        player.grapple_target = target_pos
        player.grapple_cooldown = player.grapple_cooldown_time
        
        # Create grapple hook visual effect
        player.grapple_hook = Entity(
            model='sphere',
            color=color.yellow,
            scale=0.2,
            position=player.position + Vec3(0, 1, 0)
        )
        
        print(f"Grappling to: {target_pos}")

def update_grapple():
    """Update grappling hook movement"""
    if player.is_grappling and player.grapple_target:
        # Move player towards grapple target
        direction = (player.grapple_target - player.position).normalized()
        player.position += direction * player.grapple_speed * time.dt
        
        # Update grapple hook position
        if player.grapple_hook:
            player.grapple_hook.position = player.position + Vec3(0, 1, 0)
        
        # Check if reached target
        if (player.position - player.grapple_target).length() < 3:
            end_grapple()

def end_grapple():
    """End grappling"""
    player.is_grappling = False
    player.grapple_target = None
    if player.grapple_hook:
        destroy(player.grapple_hook)
        player.grapple_hook = None

def double_jump():
    """Perform double jump"""
    if player.has_double_jump and player.double_jump_available and player.jump_count < 2:
        player.y += 2
        player.jump_count += 1
        if player.jump_count >= 2:
            player.double_jump_available = False

def reset_jump():
    """Reset jump when touching ground"""
    if player.y <= 0.1:
        player.jump_count = 0
        player.double_jump_available = True

# === Gun Model (Dynamic) ===
gun = Entity(parent=camera.ui, position=(0.5, -0.25, 1.2), scale=0.25)

def update_gun_model():
    """Update gun model based on current weapon"""
    # Clear existing gun model
    for child in gun.children[:]:
        destroy(child)
    
    # Create new model based on current weapon
    if player.current_weapon == 'pistol':
        gun_model = create_pistol_model()
    elif player.current_weapon == 'assault_rifle':
        gun_model = create_assault_rifle_model()
    elif player.current_weapon == 'laser':
        gun_model = create_laser_rifle_model()
    else:
        gun_model = create_pistol_model()  # Default
    
    # Parent the model to the gun entity
    gun_model.parent = gun
    gun_model.position = Vec3(0, 0, 0)
    gun_model.scale = 1

# Initialize gun model
update_gun_model()

# === Power-up logic ===
def spawn_powerup(type='health'):
    color_map = {'health': color.green, 'ammo': color.azure}
    pos = Vec3(random.uniform(-140, 140), 0.5, random.uniform(-140, 140))
    powerup = Entity(
        model='sphere', color=color_map[type], position=pos, scale=0.5,
        collider='sphere'
    )
    powerup.type = type
    powerups.append(powerup)

# === Bullet logic ===
class Bullet(Entity):
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
        self.lifetime = 2  # Bullet disappears after 2 seconds
        self.timer = 0

    def update(self):
        self.position += self.direction * self.speed * time.dt
        self.timer += time.dt
        
        # Destroy bullet if it goes too far or times out
        if self.timer >= self.lifetime or (self.position - player.position).length() > 100:
            if self in bullets:
                bullets.remove(self)
            destroy(self)


def shoot():
    try:
        if player.is_reloading or game_over or shop_open:
            return
        
        weapon_data = weapons[player.current_weapon]
        if player.ammo <= 0:
            reload()  # Auto-reload if out of ammo
            return
        player.ammo -= 1
        
        # Play different sounds based on weapon type
        if player.current_weapon == 'laser':
            if laser_sfx: laser_sfx.play()
        else:
            if shoot_sfx: shoot_sfx.play()

        # Spawn bullet from gun position (bottom right of screen)
        gun_pos = camera.world_position + camera.forward * 1.5 + camera.right * 0.5 - camera.up * 0.25
        bullet = Bullet(position=gun_pos, direction=camera.forward, weapon_type=player.current_weapon)
        bullets.append(bullet)

    except Exception as e:
        print(f"[ERROR 1001] Failed to shoot bullet: {e}")

# === Reload logic ===
def reload():
    if player.ammo == player.max_ammo or player.is_reloading or game_over:
        return
    player.is_reloading = True
    
    # Play different reload sounds based on weapon type
    if player.current_weapon == 'laser':
        if laser_reload_sfx: laser_reload_sfx.play()
    else:
        if reload_sfx: reload_sfx.play()
    
    invoke(finish_reload, delay=player.reload_time)

def finish_reload():
    weapon_data = weapons[player.current_weapon]
    player.ammo = weapon_data['ammo_capacity']
    player.max_ammo = weapon_data['ammo_capacity']
    player.is_reloading = False

# === Boss System ===
bosses = []
boss_attack_indicators = []

class BossAttackIndicator(Entity):
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
        # Pulse effect
        pulse = (sin(self.timer * self.pulse_speed) + 1) * 0.3 + 0.7
        self.scale = self.original_scale * pulse
        
        # Change color based on time remaining
        if self.timer > self.delay * 0.7:
            self.color = color.red
        elif self.timer > self.delay * 0.4:
            self.color = color.orange
        else:
            self.color = color.yellow
            
        # Remove when time is up
        if self.timer >= self.delay:
            if self in boss_attack_indicators:
                boss_attack_indicators.remove(self)
            destroy(self)

def spawn_boss():
    boss_type = random.choice(['titan', 'warlock', 'behemoth'])
    base = Entity(model=None, position=Vec3(random.uniform(-100, 100), 2, random.uniform(-100, 100)),
                  collider='box')
    
    if boss_type == 'titan':
        body = create_titan_boss_model()
        body.parent = base
        stats = dict(speed=3, health=500, attack_damage=40, attack_range=8, attack_cooldown=4)
        abilities = ['ground_slam', 'charge']
        
    elif boss_type == 'warlock':
        body = create_warlock_boss_model()
        body.parent = base
        stats = dict(speed=2, health=400, attack_damage=35, attack_range=12, attack_cooldown=3)
        abilities = ['magic_burst', 'teleport']
        
    else:  # behemoth
        body = create_behemoth_boss_model()
        body.parent = base
        stats = dict(speed=4, health=600, attack_damage=50, attack_range=6, attack_cooldown=5)
        abilities = ['roar', 'stomp']

    # Boss nameplate
    name_text = Text(text=f'BOSS: {boss_type.upper()}', world_parent=base, y=6, scale=2, color=color.red, billboard=True)
    health_text = Text(text=f'HP: {stats["health"]}', world_parent=base, y=5, scale=1.5, color=color.green, billboard=True)
    
    base.body = body
    base.nameplate = name_text
    base.health_text = health_text
    base.speed = stats['speed']
    base.health = stats['health']
    base.max_health = stats['health']
    base.type = boss_type
    base.attack_damage = stats['attack_damage']
    base.attack_range = stats['attack_range']
    base.attack_cooldown = stats['attack_cooldown']
    base.attack_timer = 0
    base.abilities = abilities
    base.current_ability = None
    base.ability_timer = 0
    
    bosses.append(base)
    print(f"BOSS SPAWNED: {boss_type.upper()} - HP: {stats['health']}")

def boss_ground_slam(boss):
    # Create warning indicator
    indicator = BossAttackIndicator(boss.position, 'ground_slam', delay=2.0)
    boss_attack_indicators.append(indicator)
    
    # Execute attack after delay
    def execute_slam():
        # Create shockwave effect
        shockwave = Entity(
            model='sphere',
            color=color.red,
            scale=(1, 0.1, 1),
            position=boss.position,
            alpha=0.8
        )
        
        # Damage player if in range
        if (player.position - boss.position).length() < boss.attack_range:
            player.health -= boss.attack_damage
            # Knockback effect
            knockback_dir = (player.position - boss.position).normalized()
            player.position += knockback_dir * 10
        
        # Animate shockwave
        def expand_shockwave():
            shockwave.scale += Vec3(2, 0, 2) * time.dt
            shockwave.alpha -= time.dt * 2
            if shockwave.alpha > 0:
                invoke(expand_shockwave, delay=0.05)
            else:
                destroy(shockwave)
        expand_shockwave()
    
    invoke(execute_slam, delay=2.0)

def boss_charge(boss):
    # Predict charge path
    charge_direction = (player.position - boss.position).normalized()
    charge_target = boss.position + charge_direction * 15
    
    # Create warning line
    warning_line = Entity(
        model='cube',
        color=color.red,
        scale=(15, 0.1, 1),
        position=(boss.position + charge_target) / 2,
        alpha=0.6
    )
    warning_line.look_at(charge_target)
    
    def execute_charge():
        # Move boss along charge path
        boss.position = charge_target
        
        # Damage player if hit
        if (player.position - boss.position).length() < 3:
            player.health -= boss.attack_damage
            # Heavy knockback
            knockback_dir = (player.position - boss.position).normalized()
            player.position += knockback_dir * 15
        
        destroy(warning_line)
    
    invoke(execute_charge, delay=1.5)

def boss_magic_burst(boss):
    # Create warning ring
    warning_ring = Entity(
        model='sphere',
        color=color.purple,
        scale=(boss.attack_range, 0.1, boss.attack_range),
        position=boss.position,
        alpha=0.5
    )
    
    def execute_burst():
        # Damage player if in range
        if (player.position - boss.position).length() < boss.attack_range:
            player.health -= boss.attack_damage
        
        # Visual burst effect
        burst = Entity(
            model='sphere',
            color=color.cyan,
            scale=(0.1, 0.1, 0.1),
            position=boss.position
        )
        
        def expand_burst():
            burst.scale += Vec3(1, 1, 1) * time.dt * 5
            burst.alpha -= time.dt * 2
            if burst.alpha > 0:
                invoke(expand_burst, delay=0.05)
            else:
                destroy(burst)
        expand_burst()
        
        destroy(warning_ring)
    
    invoke(execute_burst, delay=1.5)

def boss_teleport(boss):
    # Teleport to random position near player
    teleport_pos = player.position + Vec3(random.uniform(-10, 10), 0, random.uniform(-10, 10))
    
    # Teleport effect
    teleport_effect = Entity(
        model='sphere',
        color=color.purple,
        scale=(3, 3, 3),
        position=boss.position,
        alpha=0.8
    )
    
    def execute_teleport():
        boss.position = teleport_pos
        
        # Damage player if close after teleport
        if (player.position - boss.position).length() < 3:
            player.health -= boss.attack_damage // 2
        
        # Teleport arrival effect
        arrival_effect = Entity(
            model='sphere',
            color=color.cyan,
            scale=(3, 3, 3),
            position=boss.position,
            alpha=0.8
        )
        
        def fade_effect():
            arrival_effect.alpha -= time.dt * 2
            if arrival_effect.alpha > 0:
                invoke(fade_effect, delay=0.05)
            else:
                destroy(arrival_effect)
        fade_effect()
        
        destroy(teleport_effect)
    
    invoke(execute_teleport, delay=0.5)

def boss_roar(boss):
    # Create warning indicator
    indicator = BossAttackIndicator(boss.position, 'roar', delay=1.5)
    boss_attack_indicators.append(indicator)
    
    def execute_roar():
        # Stun and damage player
        if (player.position - boss.position).length() < boss.attack_range:
            player.health -= boss.attack_damage
            # Slow player temporarily
            player.speed *= 0.5
            invoke(lambda: setattr(player, 'speed', 7.5), delay=3.0)
    
    invoke(execute_roar, delay=1.5)

def boss_stomp(boss):
    # Create warning indicator
    indicator = BossAttackIndicator(boss.position, 'stomp', delay=1.0)
    boss_attack_indicators.append(indicator)
    
    def execute_stomp():
        # Heavy damage and knockback
        if (player.position - boss.position).length() < boss.attack_range:
            player.health -= boss.attack_damage
            knockback_dir = (player.position - boss.position).normalized()
            player.position += knockback_dir * 20
    
    invoke(execute_stomp, delay=1.0)

# === Enemy spawn ===
def spawn_enemy():
    enemy_type = random.choice(['grunt', 'brute', 'crawler'])
    base = Entity(model=None, position=Vec3(random.uniform(-140, 140), 1, random.uniform(-140, 140)),
                  collider='box')
    
    if enemy_type == 'grunt':
        body = create_grunt_model()
        body.parent = base
        stats = dict(speed=7.5, health=50)  # Increased by 200%
    elif enemy_type == 'brute':
        body = create_brute_model()
        body.parent = base
        stats = dict(speed=4.5, health=150)  # Increased by 200%
    else:  # crawler
        body = create_crawler_model()
        body.parent = base
        stats = dict(speed=10.5, health=30)  # Increased by 200%

    # Nameplate
    name_text = Text(text=enemy_type.upper(), world_parent=base, y=3, scale=1.5, color=color.white, billboard=True)
    base.body = body
    base.nameplate = name_text
    base.speed = stats['speed']
    base.health = stats['health']
    base.type = enemy_type
    enemies.append(base)

def spawn_wave():
    global enemies_per_wave
    for _ in range(enemies_per_wave):
        spawn_enemy()
    
    # Spawn boss every 3 waves
    if wave % 3 == 0:
        spawn_boss()
    
    wave_text.text = f"Wave: {wave}"
    for _ in range(random.randint(1,3)):
        spawn_powerup(random.choice(['health','ammo']))

# === Shop System ===
shop_panel = Panel(scale=(0.5,0.6), color=color.rgba(30,30,30,220), enabled=False)
shop_title = Text('ARMORY', parent=shop_panel, y=0.25, scale=2, color=color.yellow, origin=(0,0))
shop_desc = Text('Press 1: Pistol (Free)\nPress 2: Assault Rifle ($500)\nPress 3: Laser Rifle ($800)\nESC to close', parent=shop_panel, y=0.1, scale=1.2, origin=(0,0))
shop_money = Text('', parent=shop_panel, y=-0.18, scale=1.2, origin=(0,0))
shop_panel.enabled = False

def open_shop():
    global shop_open
    shop_open = True
    shop_panel.enabled = True
    shop_money.text = f'Your Money: ${player.money}'
    mouse.locked = False
    shop_text.text = ''

def close_shop():
    global shop_open
    shop_open = False
    shop_panel.enabled = False
    # Mouse remains unlocked - user can manually lock with M key
    shop_text.text = 'Press B for Shop'

def buy_weapon(weapon_key):
    global shop_open
    weapon_data = weapons[weapon_key]
    if player.money >= weapon_data['cost']:
        player.money -= weapon_data['cost']
        player.current_weapon = weapon_key
        # Update player stats for new weapon
        player.max_ammo = weapon_data['ammo_capacity']
        player.ammo = weapon_data['ammo_capacity']
        player.reload_time = weapon_data['reload_time']
        # Update gun model
        update_gun_model()
        close_shop()
        print(f"Purchased {weapon_data['name']} for ${weapon_data['cost']}")
    else:
        print(f"Not enough money! Need ${weapon_data['cost']}, have ${player.money}")

# === Inventory System ===
inventory_open = False
inventory_panel = Panel(scale=(0.7,0.8), color=color.rgba(20,20,20,240), enabled=False)
inventory_title = Text('INVENTORY', parent=inventory_panel, y=0.35, scale=2.5, color=color.cyan, origin=(0,0))
inventory_info = Text('', parent=inventory_panel, y=0.25, scale=1.0, color=color.white, origin=(0,0))
inventory_items = Text('', parent=inventory_panel, y=0.1, scale=0.8, color=color.white, origin=(0,0))
inventory_controls = Text('ESC to close | 1-9 to use items | S to sort', parent=inventory_panel, y=-0.35, scale=1.0, color=color.yellow, origin=(0,0))
inventory_panel.enabled = False

def open_inventory():
    global inventory_open
    inventory_open = True
    inventory_panel.enabled = True
    mouse.locked = False
    update_inventory_display()
    inventory_text.text = ''

def close_inventory():
    global inventory_open
    inventory_open = False
    inventory_panel.enabled = False
    inventory_text.text = 'Press I for Inventory'

def update_inventory_display():
    """Update the inventory display with current items"""
    if not inventory_open:
        return
    
    # Update inventory info
    inventory_info.text = f'Items: {len(player.inventory.items)}/{player.inventory.max_size}'
    
    # Display items
    if len(player.inventory.items) == 0:
        inventory_items.text = 'No items in inventory'
    else:
        items_text = ''
        for i, item in enumerate(player.inventory.items[:9]):  # Show first 9 items
            rarity_color = {
                'common': 'white',
                'uncommon': 'green', 
                'rare': 'blue',
                'legendary': 'purple'
            }.get(item.get('rarity', 'common'), 'white')
            
            items_text += f'{i+1}. {item["name"]} ({item["type"]}) - {item["description"]}\n'
        
        inventory_items.text = items_text

def use_inventory_item(item_index):
    """Use an item from inventory"""
    if 0 <= item_index < len(player.inventory.items):
        item = player.inventory.items[item_index]
        
        if item['type'] == 'consumable':
            apply_consumable_effect(item)
            player.inventory.remove_item(item)
            print(f"Used {item['name']}")
        elif item['type'] == 'weapon':
            # Equip weapon
            player.inventory.equipped_weapon = item
            print(f"Equipped {item['name']}")
        elif item['type'] == 'armor':
            # Equip armor
            player.inventory.equipped_armor = item
            print(f"Equipped {item['name']}")
        
        update_inventory_display()

# === Input ===
def input(key):
    global player
    
    # Debug: Print mouse lock status when F3 is pressed
    if key == 'f3':
        global debug_mode
        debug_mode = not debug_mode
        print(f"Debug mode: {'ON' if debug_mode else 'OFF'}")
        print(f"Mouse locked: {mouse.locked}")
        print(f"Shop open: {shop_open}")
        print(f"Inventory open: {inventory_open}")
        print(f"Pause panel enabled: {pause_panel.enabled}")
        print(f"Keybind panel enabled: {keybind_panel.enabled}")
        return
    
    if key == 'left mouse down':
        shoot()
    elif key == 'r':
        reload()
    elif key == 'q':
        application.quit()
    elif key == 'b':
        if not shop_open and not pause_panel.enabled and not inventory_open:
            open_shop()
    elif key == 'i':
        if not shop_open and not pause_panel.enabled and not inventory_open:
            open_inventory()
    elif key == 'escape':
        if shop_open:
            close_shop()
        elif inventory_open:
            close_inventory()
        elif not pause_panel.enabled:
            pause_game()
        elif pause_panel.enabled:
            resume_game()
    elif key == '1' and shop_open:
        buy_weapon('pistol')
    elif key == '2' and shop_open:
        buy_weapon('assault_rifle')
    elif key == '3' and shop_open:
        buy_weapon('laser')
    elif key == '1' and inventory_open:
        use_inventory_item(0)
    elif key == '2' and inventory_open:
        use_inventory_item(1)
    elif key == '3' and inventory_open:
        use_inventory_item(2)
    elif key == '4' and inventory_open:
        use_inventory_item(3)
    elif key == '5' and inventory_open:
        use_inventory_item(4)
    elif key == '6' and inventory_open:
        use_inventory_item(5)
    elif key == '7' and inventory_open:
        use_inventory_item(6)
    elif key == '8' and inventory_open:
        use_inventory_item(7)
    elif key == '9' and inventory_open:
        use_inventory_item(8)
    elif key == 's' and inventory_open:
        player.inventory.sort_items('rarity')
        update_inventory_display()
    elif key == 'right mouse down':
        # Aim down sights
        player.is_aiming = True
        # Move gun closer to camera for ADS effect
        gun.position = Vec3(0.2, -0.15, 0.8)
        gun.scale = 0.3
        # Make crosshair smaller and more precise
        crosshair_h.scale = (0.008, 0.001)
        crosshair_v.scale = (0.001, 0.008)
        crosshair_dot.scale = 0.002
        crosshair_dot.color = color.green
    elif key == 'right mouse up':
        # Stop aiming
        player.is_aiming = False
        # Return gun to normal position
        gun.position = Vec3(0.5, -0.25, 1.2)
        gun.scale = 0.25
        # Return crosshair to normal
        crosshair_h.scale = (0.015, 0.002)
        crosshair_v.scale = (0.002, 0.015)
        crosshair_dot.scale = 0.003
        crosshair_dot.color = color.red
    elif key == 'left shift':
        # Start sliding
        if not player.is_sliding and player.y <= 0.1:  # Only slide when on ground
            player.is_sliding = True
            player.slide_timer = 0
            # Lower camera for slide effect
            camera.y = -0.5
            # Increase speed during slide
            player.speed = player.slide_speed
    elif key == 'space':
        # Jump or double jump
        if player.y <= 0.1:  # Ground jump
            player.y += 2
            player.jump_count = 1
        else:  # Double jump
            double_jump()
    elif key == 'e':
        # Grapple hook - grapple to where cursor is pointing
        if not player.is_grappling and player.grapple_cooldown <= 0:
            # Cast a ray from camera to find where player is looking
            raycast_result = raycast(
                camera.world_position,
                camera.forward,
                distance=player.grapple_range,
                ignore=(player,)
            )
            
            if raycast_result.hit:
                # Grapple to the hit point
                grapple_target = raycast_result.world_point
                grapple_to_target(grapple_target)
                print(f"Grappling to cursor position: {grapple_target}")
            else:
                # If no hit, grapple to a point in the direction the player is looking
                grapple_target = camera.world_position + camera.forward * player.grapple_range
                grapple_to_target(grapple_target)
                print(f"Grappling to cursor direction: {grapple_target}")
    elif key == 'f':
        # Removed fullscreen button as requested by user
        pass
    elif key == 'k':
        toggle_keybinds()
    elif key == 'm':
        # Debug: Toggle mouse lock manually
        mouse.locked = not mouse.locked
        print(f"Mouse lock manually toggled: {mouse.locked}")

# === Update Loop ===
def update():
    global enemy_kills, wave, enemies_per_wave, game_over

    if player.health <= 0 and not game_over:
        game_over_text.text = 'GAME OVER\nPress Q to Quit'
        game_over = True
        bullets.clear()
        for e in enemies:
            e.speed = 0
        return

    if game_over:
        return

    # HUD
    health_bar.text = f'Health: {int(player.health)}'
    ammo_bar.text = f'Ammo: {player.ammo}/{player.max_ammo}'
    score_text.text = f'Score: {player.score}'
    money_text.text = f'Money: ${player.money}'
    weapon_text.text = f'Weapon: {weapons[player.current_weapon]["name"]}'
    
    # Movement HUD
    if player.is_wall_running:
        wall_run_text.text = f'Wall Running: {player.wall_run_duration - player.wall_run_timer:.1f}s'
        wall_run_text.color = color.green
    else:
        wall_run_text.text = 'Press W near walls to wall run'
        wall_run_text.color = color.gray
    
    if player.is_grappling:
        movement_text.text = 'Grappling!'
        movement_text.color = color.yellow
    else:
        movement_text.text = 'Press E to grapple to cursor'
        movement_text.color = color.cyan
    
    if player.grapple_cooldown > 0:
        grapple_cooldown_text.text = f'Grapple Cooldown: {player.grapple_cooldown:.1f}s'
        grapple_cooldown_text.color = color.red
    else:
        grapple_cooldown_text.text = 'Grapple Ready'
        grapple_cooldown_text.color = color.green

    # Debug information
    if debug_mode:
        debug_text = Text(
            text=f'Pos: {player.position}\nSpeed: {player.speed}\nWall Running: {player.is_wall_running}\nGrappling: {player.is_grappling}',
            position=(0.7, -0.2),
            scale=0.7,
            color=color.yellow
        )
        # Remove debug text after a short delay
        invoke(lambda: destroy(debug_text), delay=0.1)

    # Health Regen
    if player.health < player.max_health:
        player.health += time.dt * 0.5

    # Reset jump when touching ground
    reset_jump()
    
    # Ground collision check - removed slope debugging as requested
    
    # Wall running mechanics
    if not player.is_grappling and not player.is_sliding:
        wall_normal, wall = detect_wall_run()
        
        if wall_normal and held_keys['w'] and player.y > 0.5:
            if not player.is_wall_running:
                start_wall_run(wall_normal, wall)
        else:
            if player.is_wall_running:
                end_wall_run()
        
        # Update wall run timer
        if player.is_wall_running:
            player.wall_run_timer += time.dt
            if player.wall_run_timer >= player.wall_run_duration:
                end_wall_run()
    
    # Grappling mechanics
    update_grapple()
    if player.grapple_cooldown > 0:
        player.grapple_cooldown -= time.dt
    
    # Update wall run particles
    for entity in scene.entities:
        if hasattr(entity, 'update_func'):
            entity.update_func()
    
    # Sliding mechanics
    if player.is_sliding:
        player.slide_timer += time.dt
        if player.slide_timer >= player.slide_duration:
            # End slide
            player.is_sliding = False
            player.speed = 7.5  # Return to normal speed
            camera.y = 0  # Return camera to normal height
        elif held_keys['left shift'] == False:
            # End slide early if shift is released
            player.is_sliding = False
            player.speed = 7.5  # Return to normal speed
            camera.y = 0  # Return camera to normal height

    # Powerups
    for p in powerups[:]:
        if (player.position - p.position).length() < 2:
            if pickup_sfx: pickup_sfx.play()
            if p.type == 'health':
                player.health = min(player.max_health, player.health + 30)
            elif p.type == 'ammo':
                player.ammo = player.max_ammo
            destroy(p)
            powerups.remove(p)

    # Loot pickup
    for loot in loot_items_world[:]:
        if (player.position - loot.position).length() < 2:
            if pickup_loot(loot):
                loot_items_world.remove(loot)

    # Bullets
    for bullet in bullets[:]:
        try:
            bullet.update()
            
            # Check for collisions with enemies
            for e in enemies[:]:
                if e is None or bullet is None:
                    continue
                try:
                    if bullet.intersects(e).hit:
                        if hit_sfx: hit_sfx.play()
                        e.health -= bullet.damage
                        if bullet in bullets:
                            bullets.remove(bullet)
                        destroy(bullet)
                        
                        if e.health <= 0:
                            if explosion_sfx: explosion_sfx.play()
                            # Drop loot for normal enemies
                            dropped_loot = drop_loot(e.position, e.type, is_boss=False)
                            loot_items_world.extend(dropped_loot)
                            
                            enemies.remove(e)
                            destroy(e)
                            player.score += 10
                            player.money += 25  # Money reward for killing enemies
                            enemy_kills += 1
                        break  # Exit enemy loop since bullet is destroyed
                except Exception as inner_e:
                    print(f"[ERROR 1002] Bullet collision failed: {inner_e}")
            
            # Check for collisions with bosses
            for boss in bosses[:]:
                if boss is None or bullet is None:
                    continue
                try:
                    if bullet.intersects(boss).hit:
                        if hit_sfx: hit_sfx.play()
                        boss.health -= bullet.damage
                        if bullet in bullets:
                            bullets.remove(bullet)
                        destroy(bullet)
                        
                        # Update boss health display
                        if hasattr(boss, 'health_text'):
                            boss.health_text.text = f'HP: {boss.health}'
                        
                        if boss.health <= 0:
                            if explosion_sfx: explosion_sfx.play()
                            # Drop loot for bosses
                            dropped_loot = drop_loot(boss.position, boss.type, is_boss=True)
                            loot_items_world.extend(dropped_loot)
                            
                            bosses.remove(boss)
                            destroy(boss)
                            player.score += 100  # Big reward for killing boss
                            player.money += 200  # Big money reward for killing boss
                            print(f"BOSS VANQUISHED! +100 Score, +$200 Money")
                        break  # Exit boss loop since bullet is destroyed
                except Exception as inner_e:
                    print(f"[ERROR 1005] Boss bullet collision failed: {inner_e}")
        except Exception as bullet_e:
            print(f"[ERROR 1003] Bullet update failed: {bullet_e}")
            if bullet in bullets:
                bullets.remove(bullet)
            destroy(bullet)

    # Enemies movement and contact damage
    for e in enemies[:]:
        try:
            e.look_at(player.position)
            dir = (player.position - e.position).normalized()
            e.position += dir * time.dt * e.speed

            # Check collision with player
            if (e.position - player.position).length() < 1.5:
                # Deal chunk damage
                player.health -= 20  # Instant 20 HP damage
                # Bounce enemy away and launch airborne
                push_dir = (e.position - player.position).normalized()
                e.position += push_dir * 15  # push 8 units back (much farther)
                e.position.y += 10  # launch 5 units upward (airborne)
        except Exception as e_error:
            print(f"[ERROR 1004] Enemy update failed: {e_error}")
            if e in enemies:
                enemies.remove(e)
                destroy(e)

    # Boss movement and attacks
    for boss in bosses[:]:
        try:
            # Update orbiting orbs for warlock
            if boss.type == 'warlock' and hasattr(boss.body, 'children'):
                for child in boss.body.children:
                    if hasattr(child, 'orbit_speed'):
                        child.orbit_angle += child.orbit_speed * time.dt
                        child.position.x = cos(radians(child.orbit_angle)) * child.orbit_radius
                        child.position.z = sin(radians(child.orbit_angle)) * child.orbit_radius
            
            # Boss movement towards player
            if (player.position - boss.position).length() > boss.attack_range:
                boss.look_at(player.position)
                dir = (player.position - boss.position).normalized()
                boss.position += dir * time.dt * boss.speed
            
            # Boss attack logic
            boss.attack_timer += time.dt
            if boss.attack_timer >= boss.attack_cooldown:
                # Choose random ability
                ability = random.choice(boss.abilities)
                if ability == 'ground_slam':
                    boss_ground_slam(boss)
                elif ability == 'charge':
                    boss_charge(boss)
                elif ability == 'magic_burst':
                    boss_magic_burst(boss)
                elif ability == 'teleport':
                    boss_teleport(boss)
                elif ability == 'roar':
                    boss_roar(boss)
                elif ability == 'stomp':
                    boss_stomp(boss)
                
                boss.attack_timer = 0  # Reset attack timer
            
            # Boss contact damage
            if (boss.position - player.position).length() < 3:
                player.health -= 10  # Continuous damage when touching boss
                
        except Exception as boss_error:
            print(f"[ERROR 1006] Boss update failed: {boss_error}")
            if boss in bosses:
                bosses.remove(boss)
                destroy(boss)

    # Update attack indicators
    for indicator in boss_attack_indicators[:]:
        try:
            indicator.update()
        except Exception as indicator_error:
            print(f"[ERROR 1007] Attack indicator update failed: {indicator_error}")
            if indicator in boss_attack_indicators:
                boss_attack_indicators.remove(indicator)
            destroy(indicator)

    # Wave control - only advance if all enemies AND bosses are dead
    if enemy_kills >= enemies_per_wave and len(bosses) == 0:
        wave += 1
        enemy_kills = 0
        enemies_per_wave += 3
        invoke(spawn_wave, delay=3)

    # Show/hide shop UI
    shop_panel.enabled = shop_open
    if shop_open:
        shop_money.text = f'Your Money: ${player.money}'
        mouse.locked = False
    
    # Show/hide inventory UI
    inventory_panel.enabled = inventory_open
    if inventory_open:
        update_inventory_display()
        mouse.locked = False
    # Pause disables player movement
    if pause_panel.enabled:
        player.speed = 0
        mouse.locked = False
        return
    # Removed automatic mouse locking - user can manually control with M key

# === Fullscreen Button ===
# Removed fullscreen button as requested by user

# === Pause Menu ===
pause_panel = Panel(scale=(0.4,0.3), color=color.rgba(20,20,20,230), enabled=False)
pause_text = Text('PAUSED', parent=pause_panel, y=0.1, scale=2, color=color.white, origin=(0,0))
resume_btn = Button(text='Resume', parent=pause_panel, y=-0.05, scale=(0.3,0.1))
quit_btn = Button(text='Quit', parent=pause_panel, y=-0.15, scale=(0.3,0.1))
pause_panel.enabled = False

def pause_game():
    pause_panel.enabled = True
    mouse.locked = False
    application.pause()
def resume_game():
    pause_panel.enabled = False
    # Mouse remains unlocked - user can manually lock with M key
    application.resume()
def quit_game():
    application.quit()
resume_btn.on_click = resume_game
quit_btn.on_click = quit_game

# === Keybind Display ===
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

# Shop Controls (when shop is open)
shop_controls_text = Text(
    '1 - Buy Pistol (Free)\n2 - Buy Assault Rifle ($500)\n3 - Buy Laser Rifle ($800)',
    parent=keybind_panel, y=-0.65, scale=0.8, color=color.yellow, origin=(0,0)
)

# Inventory Controls (when inventory is open)
inventory_controls_text = Text(
    '1-9 - Use Items\nS - Sort by Rarity',
    parent=keybind_panel, y=-0.8, scale=0.8, color=color.cyan, origin=(0,0)
)

keybind_panel.enabled = False

def toggle_keybinds():
    keybind_panel.enabled = not keybind_panel.enabled
    if keybind_panel.enabled:
        mouse.locked = False
    else:
        # Mouse remains unlocked - user can manually lock with M key
        pass

# === Start Game ===
# Mouse is unlocked by default - user can manually lock with M key
spawn_wave()
app.run()
