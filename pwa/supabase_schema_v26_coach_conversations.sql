-- ═════════════════════════════════════════════════════════════════════
-- Muscu PRO — Migration v26 (Coach IA : conversations multiples)
-- À exécuter dans SQL Editor de Supabase. Idempotent (IF NOT EXISTS).
--
-- Objectif : passer d'un fil unique par user à un système de conversations
-- type ChatGPT (plusieurs conversations, chacune avec son propre historique).
-- ═════════════════════════════════════════════════════════════════════

-- 1) Table des conversations — une ligne par conversation.
CREATE TABLE IF NOT EXISTS public.coach_conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title      text NOT NULL DEFAULT 'Nouvelle conversation',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS coach_conversations_user_idx
  ON public.coach_conversations (user_id, updated_at DESC);

-- 2) Rattachement des messages à une conversation.
ALTER TABLE public.coach_messages
  ADD COLUMN IF NOT EXISTS conversation_id uuid
    REFERENCES public.coach_conversations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS coach_messages_conversation_idx
  ON public.coach_messages (conversation_id, created_at);

-- 3) Backfill — les messages existants (fil unique) sont regroupés dans une
--    conversation « Historique » par user, pour ne rien perdre.
DO $$
DECLARE
  u    record;
  conv uuid;
BEGIN
  FOR u IN
    SELECT DISTINCT user_id
    FROM public.coach_messages
    WHERE conversation_id IS NULL
  LOOP
    INSERT INTO public.coach_conversations (user_id, title, created_at, updated_at)
    VALUES (
      u.user_id,
      'Historique',
      COALESCE((SELECT min(created_at) FROM public.coach_messages
                 WHERE user_id = u.user_id AND conversation_id IS NULL), now()),
      COALESCE((SELECT max(created_at) FROM public.coach_messages
                 WHERE user_id = u.user_id AND conversation_id IS NULL), now())
    )
    RETURNING id INTO conv;

    UPDATE public.coach_messages
       SET conversation_id = conv
     WHERE user_id = u.user_id AND conversation_id IS NULL;
  END LOOP;
END $$;

-- 4) RLS — chaque user ne voit/modifie que ses conversations. Le backend
--    Flask utilise service_role (bypass RLS) et filtre par user_id, mais on
--    active RLS par défense en profondeur (cohérent avec les autres tables).
ALTER TABLE public.coach_conversations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "coach_conv_select_own" ON public.coach_conversations;
CREATE POLICY "coach_conv_select_own" ON public.coach_conversations
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "coach_conv_insert_own" ON public.coach_conversations;
CREATE POLICY "coach_conv_insert_own" ON public.coach_conversations
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "coach_conv_update_own" ON public.coach_conversations;
CREATE POLICY "coach_conv_update_own" ON public.coach_conversations
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "coach_conv_delete_own" ON public.coach_conversations;
CREATE POLICY "coach_conv_delete_own" ON public.coach_conversations
  FOR DELETE USING (auth.uid() = user_id);
