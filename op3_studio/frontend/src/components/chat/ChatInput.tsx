import React, { useState } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend, disabled, placeholder,
}) => {
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-gray-800 p-2 flex gap-2">
      <textarea
        rows={2}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        placeholder={placeholder ||
          "Ask about foundation design... (한국어 가능)"}
        className="flex-1 resize-none rounded bg-gray-900 border border-gray-700
                   px-3 py-2 text-sm text-gray-100 focus:outline-none
                   focus:border-op3-accent disabled:opacity-50"
      />
      <button
        onClick={submit}
        disabled={disabled || !text.trim()}
        className="px-3 py-2 rounded bg-op3-accent/20 border border-op3-accent/40
                   text-op3-accent hover:bg-op3-accent/30 disabled:opacity-50"
      >
        <Send size={16} />
      </button>
    </div>
  );
};

export default ChatInput;
