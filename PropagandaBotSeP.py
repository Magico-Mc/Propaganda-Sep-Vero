import logging
import os
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, BotCommand, BotCommandScopeChat, BotCommandScopeDefault, BotCommandScopeAllPrivateChats
from datetime import datetime, timedelta
import re
import requests
from bs4 import BeautifulSoup

try:
    from telegram.ext import Updater, CommandHandler, CallbackContext, ConversationHandler, MessageHandler, CallbackQueryHandler
    try:
        from telegram.ext import Filters
    except ImportError:
        try:
            from telegram.ext import filters as Filters
        except ImportError:
            from telegram import filters as Filters
except Exception:
    raise

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8210953537:AAHUJ91xoz3pIzvgboAwy86ka__hn-ZiHq8"
GROUP_ID = -1003382688506
PRE_MEMBERS_GROUP_ID = -1002324732088
GOOGLE_SHEET_ID = "1_w5dSHcW5dopBh16PI2LdMvqgEomR3ct0PGXfJxmL4Y"
JSON_FILE = os.environ.get('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

PRE_MEMBERS_LINK = "https://t.me/+063MK8B8OeQ0Y2Nk"

reason_requests = {}

permessi_requests = {}

pending_approvals = {}

SCEGLI_AZIONE, NOME_PROPAGANDISTA, NOME_TESSERATO, TG_TESSERATO, LAVORO_TESSERATO, IN_GAME = range(6)
RICHIEDI_PERMESSI_NICK = 6

user_data = {}

BANNED_FILE = "banned_users.txt"

MODULI_MSG_IDS = []

APPROVAL_MSG_IDS = []

def setup_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(JSON_FILE, scopes=scope)
    client = gspread.authorize(creds)
    return client

def get_foglio2():
    client = setup_google_sheets()
    return client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio2")

def carica_bannati():
    """Carica la lista degli utenti bannati"""
    banned = set()
    try:
        with open(BANNED_FILE, "r") as f:
            for line in f:
                banned.add(int(line.strip()))
    except FileNotFoundError:
        pass
    return banned

def salva_bannati(banned: set):
    """Salva la lista degli utenti bannati"""
    with open(BANNED_FILE, "w") as f:
        for uid in banned:
            f.write(f"{uid}\n")

BANNED_USERS = carica_bannati()

def start(update: Update, context: CallbackContext):
    """Comando /start - Mostra presentazione e comandi"""
    user_id = update.effective_user.id
    
    # Controlla se l'utente è bannato
    if user_id in BANNED_USERS:
        update.message.reply_text("❌ <b>Sei stato bannato dal bot.</b>", parse_mode="HTML")
        return
    
    user_name = update.effective_user.first_name or "Utente"

    keyboard = [
        [InlineKeyboardButton("🆕 Nuovo Tesseramento", callback_data="nuovo_tesseramento")],
        [InlineKeyboardButton("🔐 Richiedi Permessi", callback_data="richiedi_permessi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    presentation = (
        "🔱 <b>𝐒𝐈𝐂𝐔𝐑𝐄𝐙𝐙𝐀 𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒𝐎</b> #SeP\n\n"
        f"📥 <b>Benvenuto {user_name}!</b>\n"
        "Hai attivato il bot ufficiale della propaganda di SeP.\n\n"
        "<b>Qui trovi tutto ciò che serve per:</b>\n"
        " - Richiedere permessi per tesserare e guadagnare\n"
        " - Registrare i tesseramenti\n\n"
        "👇 <b>Usa i pulsanti qui sotto:</b>"
    )

    update.message.reply_photo(
        photo="https://ibb.co/5hgQgxRm",
        caption=presentation,
        parse_mode="HTML",
        reply_markup=reply_markup
    )

def button_callback(update: Update, context: CallbackContext):
    """Gestisce i click dei bottoni"""
    query = update.callback_query
    query.answer()
    
    if query.data == "nuovo_tesseramento":
        user_id = query.from_user.id
        user_data[user_id] = {"msg_ids": []}
        msg = query.message.reply_text(
            "▸ <b>Nick del Propagandista:</b>\n"
            "<i>(Es. SoyLeoo_)</i>",
            parse_mode="HTML"
        )
        user_data[user_id]["last_msg_id"] = msg.message_id
        return NOME_PROPAGANDISTA
    
    elif query.data == "richiedi_permessi":
        user_id = query.from_user.id
        user_data[user_id] = {"msg_ids": [], "type": "permessi"}
        msg = query.message.reply_text(
            "▸ <b>Inserisci il tuo Nick in game:</b>\n"
            "<i>(Es. SoyLeoo_)</i>",
            parse_mode="HTML"
        )
        user_data[user_id]["last_msg_id"] = msg.message_id
        return RICHIEDI_PERMESSI_NICK

def ricevi_nome_propagandista(update: Update, context: CallbackContext):
    """Riceve nome propagandista"""
    try:
        user_id = update.effective_user.id
        text = update.message.text

        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]["propagandista"] = text
        user_data[user_id]["msg_ids"] = user_data[user_id].get("msg_ids", [])
        logging.info(f"User {user_id} ha inserito propagandista: {text}")

        # Controlla se il propagandista è registrato in Foglio1
        try:
            client = setup_google_sheets()
            sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
            rows = sheet.get_all_values()
            logging.info(f"Controllo propagandista '{text}' in Foglio1. Righe totali: {len(rows)}")
            found = False
            for row in rows[1:]:  # Salta header
                if len(row) > 1 and row[1].strip() == text:  # Colonna B: Nick Tesseratore
                    found = True
                    break
            if not found:
                logging.warning(f"Propagandista '{text}' non trovato in Foglio1")
                # Cancella il messaggio dell'utente
                try:
                    update.message.delete()
                except:
                    pass

                # Cancella il messaggio della domanda precedente
                try:
                    if "last_msg_id" in user_data[user_id]:
                        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=user_data[user_id]["last_msg_id"])
                except:
                    pass

                update.message.reply_text(
                    "❌ <b>Propagandista non registrato</b>\n\n"
                    "Il propagandista inserito non è registrato nel sistema.\n"
                    "Prima di procedere con il tesseramento, devi richiedere i permessi.\n\n"
                    "Usa /start per ricominciare e selezionare '🔐 Richiedi Permessi'.",
                    parse_mode="HTML"
                )
                if user_id in user_data:
                    del user_data[user_id]
                return ConversationHandler.END
        except Exception as e:
            logging.error(f"Errore nel controllo propagandista: {e}")
            update.message.reply_text("❌ Errore nel controllo. Ricomincia con /start")
            return ConversationHandler.END

        # Cancella il messaggio dell'utente
        try:
            update.message.delete()
        except:
            pass

        # Cancella il messaggio della domanda precedente (last_msg_id)
        try:
            if "last_msg_id" in user_data[user_id]:
                context.bot.delete_message(chat_id=update.effective_chat.id, message_id=user_data[user_id]["last_msg_id"])
        except:
            pass

        # Invia prossima domanda e aggiorna last_msg_id
        msg = update.message.reply_text(
            "▸ <b>Nick del Tesserato:</b>\n"
            "<i>(Es. LoloCass)</i>",
            parse_mode="HTML"
        )
        user_data[user_id]["last_msg_id"] = msg.message_id

        return NOME_TESSERATO
    except Exception as e:
        logging.error(f"Errore in ricevi_nome_propagandista: {e}")
        update.message.reply_text("❌ Errore. Ricomincia con /start")
        return ConversationHandler.END

def ricevi_nome_tesserato(update: Update, context: CallbackContext):
    """Riceve nome tesserato"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        user_data[user_id]["tesserato"] = text
        logging.info(f"User {user_id} ha inserito tesserato: {text}")
        
        # Cancella il messaggio dell'utente
        try:
            update.message.delete()
        except:
            pass
        
        # Cancella il messaggio della domanda precedente
        try:
            if "last_msg_id" in user_data[user_id]:
                context.bot.delete_message(chat_id=update.effective_chat.id, message_id=user_data[user_id]["last_msg_id"])
        except:
            pass
        
        # Invia prossima domanda e aggiorna last_msg_id
        msg = update.message.reply_text(
            "📱 <b>Username Telegram:</b>\n"
            "<i>(Es. @SoyLe0)</i>",
            parse_mode="HTML"
        )
        user_data[user_id]["last_msg_id"] = msg.message_id
        
        return TG_TESSERATO
    except Exception as e:
        logging.error(f"Errore in ricevi_nome_tesserato: {e}")
        update.message.reply_text("❌ Errore. Ricomincia con /start")
        return ConversationHandler.END

def ricevi_tg_tesserato(update: Update, context: CallbackContext):
    """Riceve username Telegram"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        user_data[user_id]["tg"] = text
        logging.info(f"User {user_id} ha inserito TG: {text}")
        
        # Cancella il messaggio dell'utente
        try:
            update.message.delete()
        except:
            pass
        
        # Cancella il messaggio della domanda precedente
        try:
            if "last_msg_id" in user_data[user_id]:
                context.bot.delete_message(chat_id=update.effective_chat.id, message_id=user_data[user_id]["last_msg_id"])
        except:
            pass
        
        # Invia prossima domanda e aggiorna last_msg_id
        msg = update.message.reply_text(
            "💼 <b>Lavoro del Tesserato:</b>\n"
            "<i>(Es. Docente/Disoccupato)</i>",
            parse_mode="HTML"
        )
        user_data[user_id]["last_msg_id"] = msg.message_id
        
        return LAVORO_TESSERATO
    except Exception as e:
        logging.error(f"Errore in ricevi_tg_tesserato: {e}")
        update.message.reply_text("❌ Errore. Ricomincia con /start")
        return ConversationHandler.END

def ricevi_lavoro(update: Update, context: CallbackContext):
    """Riceve lavoro tesserato"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        user_data[user_id]["lavoro"] = text
        logging.info(f"User {user_id} ha inserito lavoro: {text}")
        
        # Cancella il messaggio dell'utente
        try:
            update.message.delete()
        except:
            pass
        
        # Cancella il messaggio della domanda precedente
        try:
            if "last_msg_id" in user_data[user_id]:
                context.bot.delete_message(chat_id=update.effective_chat.id, message_id=user_data[user_id]["last_msg_id"])
        except:
            pass
        
        # Bottoni si/no per in game
        keyboard = [
            [InlineKeyboardButton("✅ Si", callback_data="in_game_si"),
             InlineKeyboardButton("❌ No", callback_data="in_game_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = update.message.reply_text(
            "🎮 <b>Tesseramento in game:</b>\n"
            "<i>(Tramite /partito tessera)</i>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        user_data[user_id]["last_msg_id"] = msg.message_id
        
        return IN_GAME
    except Exception as e:
        logging.error(f"Errore in ricevi_lavoro: {e}")
        update.message.reply_text("❌ Errore. Ricomincia con /start")
        return ConversationHandler.END

def ricevi_in_game(update: Update, context: CallbackContext):
    """Riceve risposta in game"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == "in_game_si":
        user_data[user_id]["in_game"] = "✅ Si"
    else:
        user_data[user_id]["in_game"] = "❌ No"
    
    query.answer()
    
    # Mostra modulo di conferma
    mostra_modulo_conferma(query, context, user_id)
    return ConversationHandler.END

def mostra_modulo_conferma(query, context, user_id):
    """Mostra il modulo compilato con bottoni invia/cancella"""
    data = user_data[user_id]
    submitter = query.from_user
    submitter_username = f"@{submitter.username}" if submitter.username else "N/A"
    tg_val = data.get('tg') or ""
    if tg_val and not tg_val.startswith("@"):
        tg_val = "@" + tg_val
    
    modulo = (
        "📋 <b>Modulo Tesseramento</b>\n\n"
        f"▸ <b>Propagandista:</b> {data.get('propagandista', 'N/A')}\n"
        f"▸ <b>Tesserato:</b> {data.get('tesserato', 'N/A')}\n"
        f"▸ <b>Telegram:</b> {tg_val or 'N/A'}\n"
        f"▸ <b>Lavoro:</b> {data.get('lavoro', 'N/A')}\n"
        f"▸ <b>Tesserato In Game:</b> {data.get('in_game', 'N/A')}\n"
        f"▸ <b>Tesseratore:</b> {submitter_username}"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Invia", callback_data=f"invia_{user_id}"),
         InlineKeyboardButton("❌ Cancella", callback_data="cancella")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(modulo, parse_mode="HTML", reply_markup=reply_markup)

def invia_modulo(update: Update, context: CallbackContext):
    """Invia il modulo al gruppo e a Google Sheets"""
    query = update.callback_query
    user_id = int(query.data.split("_")[1])
    data = user_data[user_id]
    submitter = query.from_user
    submitter_username = f"@{submitter.username}" if submitter.username else ""

    # Invia al gruppo (con solo @ del tesseratore)
    modulo_gruppo = (
        "📋 <b>Modulo Tesseramento</b>\n\n"
        f"▸ <b>Propagandista:</b> {data.get('propagandista', 'N/A')}\n"
        f"▸ <b>Tesserato:</b> {data.get('tesserato', 'N/A')}\n"
        f"▸ <b>Telegram:</b> {data.get('tg') or 'N/A'}\n"
        f"▸ <b>Lavoro:</b> {data.get('lavoro', 'N/A')}\n"
        f"▸ <b>In-Game:</b> {data.get('in_game', 'N/A')}\n"
        f"▸ <b>Tesseratore:</b> {submitter_username}"
    )

    # Prepara bottoni approva/rifiuta
    tesserato_tg = data.get('tg') or ''
    if tesserato_tg.startswith('@'):
        tesserato_tg_no_at = tesserato_tg[1:]
    else:
        tesserato_tg_no_at = tesserato_tg
    propagandista = data.get('propagandista', '')
    keyboard = [
        [InlineKeyboardButton("✅ Approva", callback_data=f"approva_{user_id}_{tesserato_tg_no_at}_{propagandista}"),
         InlineKeyboardButton("❌ Rifiuta", callback_data=f"rifiuta_{user_id}_{tesserato_tg_no_at}_{propagandista}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        msg = context.bot.send_message(chat_id=GROUP_ID, text=modulo_gruppo, parse_mode="HTML", reply_markup=reply_markup)
        MODULI_MSG_IDS.append(msg.message_id)
    except Exception as e:
        logging.error(f"Errore nell'invio al gruppo: {e}")

    # Aggiorna la riga del tesseratore in Google Sheets (solo per tesseramenti vecchi)
    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()
        propagandista = data.get('propagandista', '')
        updated = False
        for idx, row in enumerate(rows[1:], start=2):  # Salta header, inizia da riga 2
            if len(row) > 1 and row[1] == propagandista:  # Colonna B: Nick Tesseratore
                # Aggiorna N tesseramenti questa settimana (colonna D) +1
                current_count = int(row[3]) if row[3].isdigit() else 0
                sheet.update_cell(idx, 4, current_count + 1)  # Colonna D (0-indexed 3)
                # Aggiorna Pagamento (colonna F) +1000
                current_payment = int(row[5]) if row[5].isdigit() else 0
                sheet.update_cell(idx, 6, current_payment + 1000)  # Colonna F (0-indexed 5)
                updated = True
                break
        if not updated:
            logging.warning(f"Riga per tesseratore '{propagandista}' non trovata in Foglio1")
    except Exception as e:
        logging.error(f"Errore nell'aggiornamento Foglio1: {e}")

    query.edit_message_text("<b>✅ Modulo inviato con successo!</b>", parse_mode="HTML")
    if user_id in user_data:
        del user_data[user_id]

def cancella_modulo(update: Update, context: CallbackContext):
    """Cancella il modulo"""
    query = update.callback_query
    query.answer()
    query.edit_message_text("❌ Modulo cancellato. Usa /start per ricominciare.", parse_mode="HTML")

def ricevi_nick_permessi(update: Update, context: CallbackContext):
    """Riceve nick per richiesta permessi"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        submitter = update.effective_user
        submitter_username = f"@{submitter.username}" if submitter.username else ""
        
        logging.info(f"User {user_id} ha richiesto permessi con nick: {text}")
        
        # Cancella il messaggio dell'utente
        try:
            update.message.delete()
        except:
            pass
        
        # Cancella il messaggio della domanda precedente
        try:
            if "last_msg_id" in user_data[user_id]:
                context.bot.delete_message(chat_id=update.effective_chat.id, message_id=user_data[user_id]["last_msg_id"])
        except:
            pass
        
        # Invia il modulo di richiesta permessi al gruppo (con bottoni)
        modulo_permessi = (
            "🔐 <b>Richiesta Permessi</b>\n\n"
            f"▸ <b>Nick in game:</b> <b>{text}</b>\n"
            f"▸ <b>Richiedente:</b> <b>{submitter_username}</b>\n"
            f"▸ <b>Data:</b> <b>{datetime.now().strftime('%d/%m/%Y %H:%M')}</b>"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Concluso", callback_data=f"permessi_concluso_{user_id}"),
             InlineKeyboardButton("❌ Rifiuta", callback_data=f"permessi_rifiuta_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            context.bot.send_message(chat_id=GROUP_ID, text=modulo_permessi, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logging.error(f"Errore nell'invio della richiesta permessi al gruppo: {e}")
        
        # Conferma all'utente con nuovo messaggio
        update.message.reply_text(
            "▸ <b>Richiesta inviata!</b>\n\n"
            "La tua richiesta di permessi è stata inoltrata allo staff.\n"
            "Riceverai una notifica una volta elaborata. 🔐",
            parse_mode="HTML"
        )
        
        if user_id in user_data:
            del user_data[user_id]
        
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Errore in ricevi_nick_permessi: {e}")
        update.message.reply_text("❌ Errore. Ricomincia con /start")
        return ConversationHandler.END

def permessi_concluso(update: Update, context: CallbackContext):
    """Approva la richiesta di permessi"""
    query = update.callback_query
    query.answer()

    # Estrai user_id dal callback_data
    user_id = int(query.data.split("_")[2])

    # Estrai nick dal messaggio
    message_text = query.message.text
    start = message_text.find("▸ Nick in game: ") + len("▸ Nick in game: ")
    end = message_text.find("\n", start)
    nick = message_text[start:end].strip() if start != -1 and end != -1 else ""

    # Estrai @username dal messaggio
    start = message_text.find("▸ Richiedente: ") + len("▸ Richiedente: ")
    end = message_text.find("\n", start)
    username = message_text[start:end].strip() if start != -1 and end != -1 else ""

    try:
        context.bot.send_message(
            chat_id=user_id,
            text="✅ <b>Permessi Dati!</b>\n\nLa tua richiesta di permessi è stata <b>APPROVATA</b>.\nAdesso puoi iniziare a tesserare,entra nel gruppo reparto tramite questo link https://t.me/+lEEQ84iGtMRmNmVk",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Errore nell'invio notifica approvazione: {e}")

    # Aggiungi tesseratore a Foglio1
    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        # Colonne: Data, Nick Tesseratore, @Tesseratore, N tesseramenti questa settimana, N.Tesseramenti scorsa settimana, Pagamento, Pagamento scorsa sett., Warn
        sheet.append_row([
            datetime.now().strftime('%d/%m/%Y %H:%M'),  # Data
            nick,                                       # Nick Tesseratore
            username,                                   # @Tesseratore
            0,                                          # N tesseramenti questa settimana
            0,                                          # N.Tesseramenti scorsa settimana
            0,                                          # Pagamento
            0,                                          # Pagamento scorsa sett.
            0                                           # Warn
        ])
        logging.info(f"Aggiunto tesseratore {nick} a Foglio1")
    except Exception as e:
        logging.error(f"Errore nell'aggiunta a Foglio1: {e}")

    # Modifica il messaggio nel gruppo
    query.edit_message_text(
        query.message.text + "\n\n✅ <b>CONCLUSO</b> - Permessi dati",
        parse_mode="HTML"
    )

def permessi_rifiuta(update: Update, context: CallbackContext):
    """Rifiuta la richiesta di permessi"""
    query = update.callback_query
    query.answer()
    
    # Estrai user_id dal callback_data
    user_id = int(query.data.split("_")[2])
    
    try:
        context.bot.send_message(
            chat_id=user_id,
            text="❌ <b>Permessi Rifiutati</b>\n\nLa tua richiesta di permessi è stata <b>RIFIUTATA</b>.\nContatta lo staff per ulteriori informazioni.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Errore nell'invio notifica rifiuto: {e}")
    
    # Modifica il messaggio nel gruppo
    query.edit_message_text(
        query.message.text + "\n\n❌ <b>RIFIUTATO</b> - Permessi negati",
        parse_mode="HTML"
    )

def approva_modulo(update: Update, context: CallbackContext):
    """Approva il modulo di tesseramento"""
    query = update.callback_query
    query.answer()

    # Estrai user_id e tesserato_tg dal callback_data
    parts = query.data.split("_", 3)
    user_id = int(parts[1])
    tesserato_tg = parts[2] if len(parts) > 2 else ""

    # Estrai propagandista dal testo del messaggio
    message_text = query.message.text
    start = message_text.find("▸ Propagandista: ") + len("▸ Propagandista: ")
    end = message_text.find("\n", start)
    propagandista = message_text[start:end].strip() if start != -1 and end != -1 else ""



    # Invia messaggio di approvazione al gruppo
    try:
        msg = context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"✅ <b>MODULO APPROVATO</b>\n\n"
                 f"▸ <b>Tesserato:</b> @{tesserato_tg}\n\n"
                 "Il tesseramento è stato approvato.",
            parse_mode="HTML"
        )
        APPROVAL_MSG_IDS.append(msg.message_id)
    except Exception as e:
        logging.error(f"Errore nell'invio messaggio approvazione al gruppo: {e}")

    # Genera link di invito singolo uso se il bot è admin del gruppo pre-membri
    one_time_link = None
    if PRE_MEMBERS_GROUP_ID:
        try:
            # Crea link di invito con limite di 1 membro e scadenza di 24 ore
            invite_link = context.bot.create_chat_invite_link(
                chat_id=PRE_MEMBERS_GROUP_ID,
                member_limit=1,
                expire_date=datetime.now() + timedelta(hours=24),
                name=f"Invito per @{tesserato_tg}"
            )
            one_time_link = invite_link.invite_link
            logging.info(f"Creato link singolo uso per @{tesserato_tg}: {one_time_link}")
        except Exception as e:
            logging.error(f"Errore nella creazione del link di invito: {e}")
            one_time_link = None

    # Invia messaggio al tesseratore con i link
    try:
        message_text = f"✅ <b>Modulo Approvato!</b>\n\n"
        message_text += f"Il tuo modulo per @{tesserato_tg} è stato approvato.\n\n"

        if one_time_link:
            message_text += f"🔐 <b>Link Singolo Uso (24h):</b> {one_time_link}\n"
            message_text += f"<i>Questo link può essere usato solo una volta e scade tra 24 ore,condividilo con il tesserato per farlo unire al gruppo.</i>\n\n"
        else:
            message_text += f"📤 <b>Condividi questo link con @{tesserato_tg}</b> per farlo unire al gruppo pre-membri.\n\n"

        context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Errore nell'invio link al tesseratore: {e}")

    # Modifica il messaggio originale
    query.edit_message_text(
        query.message.text + "\n\n✅ <b>APPROVATO</b>",
        parse_mode="HTML"
    )

def rifiuta_modulo(update: Update, context: CallbackContext):
    """Rifiuta il modulo di tesseramento chiedendo il motivo"""
    query = update.callback_query
    query.answer()

    # Estrai user_id e tesserato_tg dal callback_data
    parts = query.data.split("_")
    user_id = int(parts[1])
    tesserato_tg = parts[2] if len(parts) > 2 else ""

    # Chiedi il motivo con reply
    try:
        msg = context.bot.send_message(
            chat_id=GROUP_ID,
            text="❌ <b>RIFIUTO MODULO</b>\n\n"
                 f"▸ <b>Tesserato:</b> @{tesserato_tg}\n\n"
                 "Rispondi a questo messaggio con il motivo del rifiuto.",
            parse_mode="HTML",
            reply_to_message_id=query.message.message_id
        )
        APPROVAL_MSG_IDS.append(msg.message_id)

        # Memorizza la richiesta di motivo rifiuto
        reason_requests[msg.message_id] = {
            "user_id": user_id,
            "tesserato_tg": tesserato_tg,
            "original_message": query.message
        }
    except Exception as e:
        logging.error(f"Errore nell'invio richiesta motivo rifiuto: {e}")

def gestisci_risposta_motivazione(update: Update, context: CallbackContext):
    """Gestisce la risposta con il motivo del rifiuto"""
    if update.message.reply_to_message and update.message.reply_to_message.message_id in reason_requests:
        request_data = reason_requests[update.message.reply_to_message.message_id]
        user_id = request_data["user_id"]
        tesserato_tg = request_data["tesserato_tg"]
        motivo = update.message.text

        # Invia messaggio di rifiuto al gruppo
        try:
            context.bot.send_message(
                chat_id=GROUP_ID,
                text=f"❌ <b>MODULO RIFIUTATO</b>\n\n"
                     f"▸ <b>Tesserato:</b> @{tesserato_tg}\n"
                     f"▸ <b>Motivo:</b> {motivo}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Errore nell'invio messaggio rifiuto: {e}")

        # Invia motivo rifiuto in privato al tesseratore
        try:
            context.bot.send_message(
                chat_id=user_id,
                text=f"❌ <b>Modulo Rifiutato</b>\n\n"
                     f"Il tuo modulo per @{tesserato_tg} è stato rifiutato.\n\n"
                     f"📝 <b>Motivo:</b> {motivo}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Errore nell'invio motivo rifiuto al tesseratore: {e}")

        # Modifica il messaggio originale
        try:
            context.bot.edit_message_text(
                chat_id=GROUP_ID,
                message_id=request_data["original_message"].message_id,
                text=request_data["original_message"].text + "\n\n❌ <b>RIFIUTATO</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Errore nella modifica messaggio originale: {e}")

        # Rimuovi dalla lista delle richieste
        del reason_requests[update.message.reply_to_message.message_id]

def cmd_totale(update: Update, context: CallbackContext):
    """Calcola il totale dei pagamenti di questa settimana per tesseratore"""
    if update.effective_chat.id != GROUP_ID:
        return

    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()

        # Salta l'header (riga 0)
        tessera_dict = {}
        for row in rows[1:]:
            if len(row) > 5:
                tesseratore = row[1]  # Colonna B: Nick Tesseratore
                pagamento = int(row[5]) if row[5].isdigit() else 0  # Colonna F: Pagamento questa settimana
                if tesseratore and pagamento > 0:
                    tessera_dict[tesseratore] = pagamento

        if not tessera_dict:
            update.message.reply_text("▸ <b>Nessun pagamento questa settimana</b>", parse_mode="HTML")
            return

        # Costruisci il messaggio
        testo = "💰 <b>Pagamenti Questa Settimana</b>\n\n"
        totale = 0
        for tesseratore, importo in sorted(tessera_dict.items()):
            testo += f"▸ <b>{tesseratore}:</b> €{importo}\n"
            totale += importo

        testo += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n▸ <b>Totale:</b> €{totale}"

        update.message.reply_text(testo, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Errore in /Totale: {e}")
        update.message.reply_text("❌ Errore nel calcolo", parse_mode="HTML")

def cmd_totalescorso(update: Update, context: CallbackContext):
    """Calcola il totale dei pagamenti della settimana scorsa per tesseratore"""
    if update.effective_chat.id != GROUP_ID:
        return

    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()

        # Salta l'header (riga 0)
        tessera_dict = {}
        for row in rows[1:]:
            if len(row) > 6:
                tesseratore = row[1]  # Colonna B: Nick Tesseratore
                pagamento_scorsa = int(row[6]) if row[6].isdigit() else 0  # Colonna G: Pagamento scorsa sett.
                if tesseratore and pagamento_scorsa > 0:
                    tessera_dict[tesseratore] = pagamento_scorsa

        if not tessera_dict:
            update.message.reply_text("▸ <b>Nessun pagamento settimana scorsa</b>", parse_mode="HTML")
            return

        # Costruisci il messaggio
        testo = "💰 <b>Pagamenti Settimana Scorsa</b>\n\n"
        totale = 0
        for tesseratore, importo in sorted(tessera_dict.items()):
            testo += f"▸ <b>{tesseratore}:</b> €{importo}\n"
            totale += importo

        testo += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n▸ <b>Totale:</b> €{totale}"

        update.message.reply_text(testo, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Errore in /Totalescorso: {e}")
        update.message.reply_text("❌ Errore nel calcolo", parse_mode="HTML")

def cmd_cancella(update: Update, context: CallbackContext):
    """Azzera i tesseramenti della settimana scorsa e i messaggi nel gruppo"""
    if update.effective_chat.id != GROUP_ID:
        return

    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()

        # Reset warns on 1st of month
        if datetime.now().day == 1:
            for idx, row in enumerate(rows[1:], start=2):
                if len(row) > 7:
                    sheet.update_cell(idx, 8, 0)

        # Azzera colonne E (N tesseramenti scorsa settimana) e G (Pagamento scorsa sett.) per tutte le righe
        for idx, row in enumerate(rows[1:], start=2):  # Inizia da riga 2 (skip header)
            if len(row) > 7:
                # Increment warn if inactive (E==0)
                if row[4].isdigit() and int(row[4]) == 0:
                    current_warn = int(row[7]) if row[7].isdigit() else 0
                    sheet.update_cell(idx, 8, current_warn + 1)
            if len(row) > 6:
                sheet.update_cell(idx, 5, 0)  # Colonna E (0-indexed 4)
                sheet.update_cell(idx, 7, 0)  # Colonna G (0-indexed 6)

        # Cancella i messaggi dei moduli tesseramenti nel gruppo
        deleted = 0
        for msg_id in MODULI_MSG_IDS[:]:
            try:
                context.bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                deleted += 1
            except Exception:
                pass
        MODULI_MSG_IDS.clear()

        # Cancella i messaggi di approvazione/rifiuto nel gruppo
        for msg_id in APPROVAL_MSG_IDS[:]:
            try:
                context.bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                deleted += 1
            except Exception:
                pass
        APPROVAL_MSG_IDS.clear()
        update.message.reply_text(
            f"▸ <b>Azzera i tesseramenti della settimana scorsa</b>\n"
            f"▸ <b>Cancellati {deleted} moduli dal gruppo</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Errore in /Cancella: {e}")
        update.message.reply_text("❌ Errore nell'azzeramento", parse_mode="HTML")

def cmd_cancella_tutto(update: Update, context: CallbackContext):
    """Azzera tutti i tesseramenti e tutti i messaggi nel gruppo"""
    if update.effective_chat.id != GROUP_ID:
        return

    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()

        # Azzera colonne D, E, F, G per tutte le righe
        for idx, row in enumerate(rows[1:], start=2):  # Inizia da riga 2 (skip header)
            if len(row) > 6:
                sheet.update_cell(idx, 4, 0)  # Colonna D (0-indexed 3)
                sheet.update_cell(idx, 5, 0)  # Colonna E (0-indexed 4)
                sheet.update_cell(idx, 6, 0)  # Colonna F (0-indexed 5)
                sheet.update_cell(idx, 7, 0)  # Colonna G (0-indexed 6)

        # Cancella tutti i messaggi dei moduli tesseramenti nel gruppo
        deleted = 0
        for msg_id in MODULI_MSG_IDS[:]:
            try:
                context.bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                deleted += 1
            except Exception:
                pass
        MODULI_MSG_IDS.clear()

        # Cancella i messaggi di approvazione/rifiuto nel gruppo
        for msg_id in APPROVAL_MSG_IDS[:]:
            try:
                context.bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                deleted += 1
            except Exception:
                pass
        APPROVAL_MSG_IDS.clear()
        update.message.reply_text(
            f"▸ <b>Azzera tutti i tesseramenti</b>\n"
            f"▸ <b>Cancellati {deleted} moduli dal gruppo</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Errore in /CancellaTutto: {e}")
        update.message.reply_text("❌ Errore nell'azzeramento", parse_mode="HTML")

def cmd_togliadd(update: Update, context: CallbackContext):
    """Banna un utente dal bot"""
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        update.message.reply_text("▸ <b>Uso:</b> /togliadd @username", parse_mode="HTML")
        return

    username = context.args[0]
    if not username.startswith("@"):
        update.message.reply_text("▸ <b>Usa @username</b>", parse_mode="HTML")
        return

    try:
        member = context.bot.get_chat_member(chat_id=GROUP_ID, user_id=username)
        user_id = member.user.id
        BANNED_USERS.add(user_id)
        salva_bannati(BANNED_USERS)
        update.message.reply_text(f"▸ <b>Utente {username} bannato</b>", parse_mode="HTML")
    except Exception as e:
        update.message.reply_text("▸ <b>Utente non trovato nel gruppo</b>", parse_mode="HTML")

def cmd_togliadd_id(update: Update, context: CallbackContext):
    """Banna un utente per ID"""
    if update.effective_chat.id != GROUP_ID:
        return
    
    if not context.args:
        update.message.reply_text("▸ <b>Uso:</b> /togliadd_id <user_id>", parse_mode="HTML")
        return
    
    try:
        user_id = int(context.args[0])
        BANNED_USERS.add(user_id)
        salva_bannati(BANNED_USERS)
        update.message.reply_text(f"▸ <b>Utente {user_id} bannato</b>", parse_mode="HTML")
    except ValueError:
        update.message.reply_text("▸ <b>ID non valido</b>", parse_mode="HTML")

def cmd_add(update: Update, context: CallbackContext):
    """Toglie il ban a un utente per ID o username"""
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        update.message.reply_text("▸ <b>Uso:</b> /add <user_id> o /add @username", parse_mode="HTML")
        return

    arg = context.args[0]
    if arg.startswith("@"):
        try:
            member = context.bot.get_chat_member(chat_id=GROUP_ID, user_id=arg)
            user_id = member.user.id
        except Exception as e:
            update.message.reply_text("▸ <b>Utente non trovato nel gruppo</b>", parse_mode="HTML")
            return
    else:
        try:
            user_id = int(arg)
        except ValueError:
            update.message.reply_text("▸ <b>ID non valido</b>", parse_mode="HTML")
            return

    if user_id in BANNED_USERS:
        BANNED_USERS.remove(user_id)
        salva_bannati(BANNED_USERS)
        update.message.reply_text(f"▸ <b>Ban rimosso per utente {arg}</b>", parse_mode="HTML")
    else:
        update.message.reply_text(f"▸ <b>Utente {arg} non è bannato</b>", parse_mode="HTML")

def cmd_listaban(update: Update, context: CallbackContext):
    """Lista gli utenti bannati"""
    if update.effective_chat.id != GROUP_ID:
        return

    if not BANNED_USERS:
        update.message.reply_text("▸ <b>Nessun utente bannato</b>", parse_mode="HTML")
        return

    testo = "🚫 <b>Utenti Bannati</b>\n\n"
    for idx, uid in enumerate(sorted(BANNED_USERS), 1):
        testo += f"▸ <b>{idx}.</b> ID: {uid}\n"

    update.message.reply_text(testo, parse_mode="HTML")

def cmd_3warn(update: Update, context: CallbackContext):
    """Rimuovi tesseratori con 3+ warns"""
    if update.effective_chat.id != GROUP_ID:
        return

    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()

        to_delete = []
        removed = []
        for idx, row in enumerate(rows[1:], start=2):
            if len(row) > 7 and row[7].isdigit() and int(row[7]) >= 3:
                to_delete.append(idx)
                removed.append(row[1])

        for idx in reversed(to_delete):
            sheet.delete_row(idx)

        if removed:
            update.message.reply_text(f"▸ <b>Rimossi tesseratori con 3+ warns:</b> {', '.join(removed)}", parse_mode="HTML")
        else:
            update.message.reply_text("▸ <b>Nessun tesseratore con 3+ warns</b>", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Errore in /3warn: {e}")
        update.message.reply_text("❌ Errore", parse_mode="HTML")

def cmd_listawarn(update: Update, context: CallbackContext):
    """Lista tesseratori con warns"""
    if update.effective_chat.id != GROUP_ID:
        return

    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()

        warn_list = []
        for row in rows[1:]:
            if len(row) > 7 and row[7].isdigit() and int(row[7]) >= 1:
                nick = row[1]
                warns = int(row[7])
                warn_list.append(f"▸ <b>{nick}:</b> {warns} warn")

        if warn_list:
            testo = "⚠️ <b>Tesseratori con warns:</b>\n\n" + "\n".join(warn_list)
        else:
            testo = "✅ <b>Nessun tesseratore con warns</b>"

        update.message.reply_text(testo, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Errore in /listawarn: {e}")
        update.message.reply_text("❌ Errore", parse_mode="HTML")

def cmd_warna(update: Update, context: CallbackContext):
    """Aggiungi warn a tesseratore"""
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        update.message.reply_text("▸ <b>Uso:</b> /warna <nick_tesseratore>", parse_mode="HTML")
        return

    nick = context.args[0]

    try:
        client = setup_google_sheets()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Foglio1")
        rows = sheet.get_all_values()

        updated = False
        for idx, row in enumerate(rows[1:], start=2):
            if len(row) > 1 and row[1] == nick:
                current_warn = int(row[7]) if len(row) > 7 and row[7].isdigit() else 0
                sheet.update_cell(idx, 8, current_warn + 1)
                updated = True
                break

        if updated:
            update.message.reply_text(f"▸ <b>Aggiunto 1 warn a {nick}</b>", parse_mode="HTML")
        else:
            update.message.reply_text(f"▸ <b>Tesseratore {nick} non trovato</b>", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Errore in /warna: {e}")
        update.message.reply_text("❌ Errore", parse_mode="HTML")

def cmd_help(update: Update, context: CallbackContext):
    """Mostra la lista dei comandi disponibili nel gruppo"""
    if update.effective_chat.id != GROUP_ID:
        return
    testo = (
        "📋 <b>Comandi disponibili:</b>\n\n"
        "▸ <b>/Totale</b> - Calcola il pagamento totale per ogni tesseratore\n"
        "▸ <b>/Cancella</b> - Cancella i tesseramenti e moduli della settimana precedente\n"
        "▸ <b>/CancellaTutto</b> - Cancella tutti i tesseramenti e moduli\n"
        "▸ <b>/togliadd_id &lt;@utente&gt;</b> - Bannare utente dal bot\n"
        "▸ <b>/add &lt;@utente&gt;</b> - Rimuovi ban utente\n"
        "▸ <b>/listaban</b> - Lista utenti bannati\n"
        "▸ <b>/help</b> - Mostra questo elenco\n"
    )
    update.message.reply_text(testo, parse_mode="HTML")

def set_bot_commands(updater):
    # Telegram bot commands must be lowercase and without special chars or spaces
    commands = [
        BotCommand("totale", "Calcola il pagamento totale per ogni tesseratore"),
        BotCommand("cancella", "Cancella i tesseramenti e moduli della settimana precedente"),
        BotCommand("cancellatutto", "Cancella tutti i tesseramenti e moduli"),
        BotCommand("togliadd_id", "Banna utente dal bot"),
        BotCommand("add", "Rimuovi ban utente"),
        BotCommand("listaban", "Lista utenti bannati"),
        BotCommand("3warn", "Rimuovi tesseratori con 3 warns"),
        BotCommand("listawarn", "Lista tesseratori con warns"),
        BotCommand("warna", "Aggiungi warn a tesseratore"),
        BotCommand("help", "Mostra la lista dei comandi"),
    ]
    # Explicitly hide commands in private chats
    updater.bot.set_my_commands([], scope=BotCommandScopeAllPrivateChats())
    # Set commands only for the group chat
    updater.bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=GROUP_ID))

def main():
    updater = Updater(TOKEN)
    dp = getattr(updater, "dispatcher", None)
    if dp is None:
        logging.error("Dispatcher non disponibile nella tua versione di python-telegram-bot.")
        return

    set_bot_commands(updater)

    # Handler per la conversazione TESSERAMENTO
    conv_handler_tesseramento = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_callback, pattern="^nuovo_tesseramento$")
        ],
        states={
            NOME_PROPAGANDISTA: [
                MessageHandler(Filters.text & ~Filters.command, ricevi_nome_propagandista),
                CallbackQueryHandler(button_callback, pattern="^nuovo_tesseramento$")
            ],
            NOME_TESSERATO: [
                MessageHandler(Filters.text & ~Filters.command, ricevi_nome_tesserato),
                CallbackQueryHandler(button_callback, pattern="^nuovo_tesseramento$")
            ],
            TG_TESSERATO: [
                MessageHandler(Filters.text & ~Filters.command, ricevi_tg_tesserato),
                CallbackQueryHandler(button_callback, pattern="^nuovo_tesseramento$")
            ],
            LAVORO_TESSERATO: [
                MessageHandler(Filters.text & ~Filters.command, ricevi_lavoro),
                CallbackQueryHandler(button_callback, pattern="^nuovo_tesseramento$")
            ],
            IN_GAME: [CallbackQueryHandler(ricevi_in_game)],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    # Handler per la conversazione RICHIEDI PERMESSI
    conv_handler_permessi = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern="^richiedi_permessi$")
        ],
        states={
            RICHIEDI_PERMESSI_NICK: [
                MessageHandler(Filters.text & ~Filters.command, ricevi_nick_permessi)
            ],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    dp.add_handler(conv_handler_tesseramento)
    dp.add_handler(conv_handler_permessi)
    dp.add_handler(CallbackQueryHandler(invia_modulo, pattern="^invia_"))
    dp.add_handler(CallbackQueryHandler(cancella_modulo, pattern="^cancella$"))
    dp.add_handler(CallbackQueryHandler(permessi_concluso, pattern="^permessi_concluso_"))
    dp.add_handler(CallbackQueryHandler(permessi_rifiuta, pattern="^permessi_rifiuta_"))
    dp.add_handler(CallbackQueryHandler(approva_modulo, pattern="^approva_"))
    dp.add_handler(CallbackQueryHandler(rifiuta_modulo, pattern="^rifiuta_"))
    dp.add_handler(MessageHandler(Filters.reply, gestisci_risposta_motivazione))

    # Aggiungi i nuovi comandi del gruppo
    dp.add_handler(CommandHandler("Totale", cmd_totale))
    dp.add_handler(CommandHandler("Cancella", cmd_cancella))
    dp.add_handler(CommandHandler("CancellaTutto", cmd_cancella_tutto))
    dp.add_handler(CommandHandler("togliadd_id", cmd_togliadd_id))
    dp.add_handler(CommandHandler("add", cmd_add))
    dp.add_handler(CommandHandler("listaban", cmd_listaban))
    dp.add_handler(CommandHandler("3warn", cmd_3warn))
    dp.add_handler(CommandHandler("listawarn", cmd_listawarn))
    dp.add_handler(CommandHandler("warna", cmd_warna))
    dp.add_handler(CommandHandler("help", cmd_help))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
