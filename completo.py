import time
import os
import json
from telegram import Update, ForceReply, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import logging

TOKEN = '1996000702:AAGvnP6faCdYGOOy_zqzQS-I9eCNGDgk41I'
GRUPO_ID = -1001436626455  # ID do grupo ou chat onde as mensagens serão enviadas
USUARIO_ID = 1310302765
DOWNLOADS_DIR = 'teste'  # Nome da pasta onde os arquivos serão armazenados
ARQUIVO_JSON = 'mensagens.json'  # Nome do arquivo JSON para armazenar as mensagens

# Configura o logger do Telegram para exibir mensagens de aviso e erro
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.WARNING)

# Cria a pasta de downloads, se não existir
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Carrega as mensagens do arquivo JSON
def carregar_mensagens():
    try:
        with open(ARQUIVO_JSON, 'r') as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        return []

# Salva as mensagens no arquivo JSON
def salvar_mensagens(mensagens):
    with open(ARQUIVO_JSON, 'w') as arquivo:
        json.dump(mensagens, arquivo)

# Handler para o comando /adicionar
def adicionar(update: Update, context):
    chat_id = update.effective_chat.id
    if chat_id == GRUPO_ID or chat_id == USUARIO_ID:
        update.message.reply_text("Digite o nome da mensagem:")
        return 1
    else:
        update.message.reply_text("Esse comando só pode ser usado no grupo.")

# Handler para obter o nome da mensagem
def adicionar_nome(update: Update, context):
    context.user_data['nome'] = update.message.text
    update.message.reply_text("Digite a descrição da mensagem:")
    return 2

# Handler para obter a descrição da mensagem
def adicionar_descricao(update: Update, context):
    context.user_data['descricao'] = update.message.text
    update.message.reply_text("Envie uma foto para a mensagem (opcional), ou use /skip para pular.")
    return 3

# Handler para obter a foto da mensagem
def adicionar_foto(update: Update, context):
    if update.message.photo:
        context.user_data['foto'] = update.message.photo[-1].file_id
    update.message.reply_text("Envie um vídeo para a mensagem (opcional), ou use /skip para pular.")
    return 4

# Handler para obter o vídeo da mensagem
def adicionar_video(update: Update, context):
    if update.message.video:
        context.user_data['video'] = update.message.video.file_id

    mensagem = {
        'nome': context.user_data['nome'],
        'descricao': context.user_data['descricao'],
        'foto': context.user_data.get('foto'),
        'video': context.user_data.get('video')
    }
    mensagens = carregar_mensagens()
    mensagens.append(mensagem)
    salvar_mensagens(mensagens)

    context.user_data.clear()
    update.message.reply_text("Mensagem adicionada com sucesso!")

    return ConversationHandler.END

# Handler para pular a etapa atual
def pular_etapa(update: Update, context):
    update.message.reply_text("Etapa pulada.")

    if context.user_data.get('foto') is None:
        update.message.reply_text("Envie uma foto para a mensagem (opcional), ou use /skip para pular.")
        return 3
    elif context.user_data.get('video') is None:
        update.message.reply_text("Envie um vídeo para a mensagem (opcional), ou use /skip para pular.")
        return 4

    return adicionar_video(update, context)

# Handler para o comando /enviar
def enviar(update: Update, context):
    chat_id = update.effective_chat.id
    if chat_id == GRUPO_ID or chat_id == USUARIO_ID:
        context.job_queue.run_once(enviar_mensagens_fila, 0, context=context)
    else:
        update.message.reply_text("Esse comando só pode ser usado no grupo.")


def enviar_mensagens_fila(context):
    mensagens = carregar_mensagens()
    if len(mensagens) == 0:
        logar("Nenhuma mensagem para enviar.")
        return

    if context.bot_data.get('last_message_id'):
        last_message_id = context.bot_data['last_message_id']
        context.bot.delete_message(chat_id=GRUPO_ID, message_id=last_message_id)

    mensagem = mensagens.pop(0)
    descricao = mensagem.get('descricao', '')
    foto = mensagem.get('foto')
    video = mensagem.get('video')

    if foto:
        foto_obj = context.bot.get_file(foto)
        foto_obj.download(os.path.join(DOWNLOADS_DIR, "foto.jpg"))
        with open(os.path.join(DOWNLOADS_DIR, "foto.jpg"), 'rb') as foto_file:
            mensagem_enviada = context.bot.send_photo(GRUPO_ID, photo=foto_file, caption=descricao)

    if video:
        video_obj = context.bot.get_file(video)
        video_obj.download(os.path.join(DOWNLOADS_DIR, "video.mp4"))
        with open(os.path.join(DOWNLOADS_DIR, "video.mp4"), 'rb') as video_file:
            mensagem_enviada = context.bot.send_video(GRUPO_ID, video=video_file, caption=descricao)

    logar(f"Mensagem enviada:\nNome: {mensagem['nome']}\nDescrição: {descricao}")

    context.bot_data['last_message_id'] = mensagem_enviada.message_id

    mensagens.append(mensagem)  # Adiciona a mensagem novamente ao final da fila

    salvar_mensagens(mensagens)
    time.sleep(300)  # Aguarda 300 segundos antes de enviar a próxima mensagem
    context.job_queue.run_once(enviar_mensagens_fila, 0, context=context)  # Executa novamente após 300 segundos


# Função para exibir logs
def logar(mensagem):
    print(mensagem)

# Função principal
def main():
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('adicionar', adicionar)],
        states={
            1: [MessageHandler(Filters.text & ~Filters.command, adicionar_nome)],
            2: [MessageHandler(Filters.text & ~Filters.command, adicionar_descricao)],
            3: [MessageHandler(Filters.photo | Filters.command("skip"), adicionar_foto)],
            4: [MessageHandler(Filters.video | Filters.command("skip"), adicionar_video)]
        },
        fallbacks=[CommandHandler('skip', pular_etapa)],
        allow_reentry=True
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('enviar', enviar))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
