//+------------------------------------------------------------------+
//| GoldAIJson.mqh                                                   |
//| Minimal JSON helpers for the GoldAI decision file.               |
//| No external libraries. Tuned for a known, modest schema, but     |
//| the walker is depth-aware so braces inside strings are safe.     |
//+------------------------------------------------------------------+
#ifndef GOLD_AI_JSON_MQH
#define GOLD_AI_JSON_MQH

//+------------------------------------------------------------------+
//| Skip whitespace; return false if we ran off the end.             |
//+------------------------------------------------------------------+
bool JsonSkipWs(const string &s, int &pos)
  {
   const int n = StringLen(s);
   while(pos < n)
     {
      const ushort c = StringGetCharacter(s, pos);
      if(c != ' ' && c != '\t' && c != '\r' && c != '\n')
         return(true);
      pos++;
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Advance over a JSON string starting at the opening quote.        |
//| On success pos sits just after the closing quote.                |
//+------------------------------------------------------------------+
bool JsonSkipString(const string &s, int &pos)
  {
   const int n = StringLen(s);
   if(pos >= n || StringGetCharacter(s, pos) != '"')
      return(false);
   pos++;
   bool escape = false;
   while(pos < n)
     {
      const ushort c = StringGetCharacter(s, pos);
      pos++;
      if(escape)
        {
         escape = false;
         continue;
        }
      if(c == '\\')
        {
         escape = true;
         continue;
        }
      if(c == '"')
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Hex digit to value, or -1 if not hex.                            |
//+------------------------------------------------------------------+
int JsonHexValue(const ushort c)
  {
   if(c >= '0' && c <= '9')
      return(c - '0');
   if(c >= 'A' && c <= 'F')
      return(c - 'A' + 10);
   if(c >= 'a' && c <= 'f')
      return(c - 'a' + 10);
   return(-1);
  }

//+------------------------------------------------------------------+
//| Unescape a JSON string body (no surrounding quotes).             |
//+------------------------------------------------------------------+
string JsonUnescape(const string &body)
  {
   string out = "";
   const int n = StringLen(body);
   int i = 0;
   while(i < n)
     {
      const ushort c = StringGetCharacter(body, i);
      if(c != '\\' || i + 1 >= n)
        {
         out += ShortToString(c);
         i++;
         continue;
        }
      const ushort e = StringGetCharacter(body, i + 1);
      i += 2;
      switch(e)
        {
         case '"':  out += "\""; break;
         case '\\': out += "\\"; break;
         case '/':  out += "/";  break;
         case 'b':  out += ShortToString((ushort)8);  break;
         case 'f':  out += ShortToString((ushort)12); break;
         case 'n':  out += "\n"; break;
         case 'r':  out += "\r"; break;
         case 't':  out += "\t"; break;
         case 'u':
           {
            if(i + 4 > n)
               break;
            int cp = 0;
            bool ok = true;
            for(int h = 0; h < 4; h++)
              {
               const int v = JsonHexValue(StringGetCharacter(body, i + h));
               if(v < 0)
                 {
                  ok = false;
                  break;
                 }
               cp = (cp << 4) + v;
              }
            if(ok)
               out += ShortToString((ushort)cp);
            i += 4;
            break;
           }
         default:
            out += ShortToString(e);
            break;
        }
     }
   return(out);
  }

//+------------------------------------------------------------------+
//| Read a JSON string at pos (must be on the opening quote).        |
//| Returns the unescaped body and advances pos past the close.      |
//+------------------------------------------------------------------+
bool JsonReadString(const string &s, int &pos, string &out)
  {
   const int n = StringLen(s);
   if(pos >= n || StringGetCharacter(s, pos) != '"')
      return(false);
   const int start_body = pos + 1;
   int scan = pos;
   if(!JsonSkipString(s, scan))
      return(false);
   // scan now sits just after the closing quote
   const int body_len = (scan - 1) - start_body;
   string body = "";
   if(body_len > 0)
      body = StringSubstr(s, start_body, body_len);
   out = JsonUnescape(body);
   pos = scan;
   return(true);
  }

//+------------------------------------------------------------------+
//| Read a balanced {...} or [...] value, respecting strings.        |
//| pos must sit on the opening bracket. Returns the slice           |
//| including the brackets, and advances pos past it.                |
//+------------------------------------------------------------------+
bool JsonReadBalanced(const string &s, int &pos, string &out)
  {
   const int n = StringLen(s);
   if(pos >= n)
      return(false);
   const ushort open = StringGetCharacter(s, pos);
   ushort close;
   if(open == '{')
      close = '}';
   else if(open == '[')
      close = ']';
   else
      return(false);

   const int start = pos;
   int depth = 0;
   bool in_string = false;
   bool escape = false;
   while(pos < n)
     {
      const ushort c = StringGetCharacter(s, pos);
      pos++;
      if(in_string)
        {
         if(escape)
           {
            escape = false;
            continue;
           }
         if(c == '\\')
           {
            escape = true;
            continue;
           }
         if(c == '"')
            in_string = false;
         continue;
        }
      if(c == '"')
        {
         in_string = true;
         continue;
        }
      if(c == open)
         depth++;
      else if(c == close)
        {
         depth--;
         if(depth == 0)
           {
            out = StringSubstr(s, start, pos - start);
            return(true);
           }
        }
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Read any JSON value starting at pos; advances pos past it.       |
//| For strings, 'out' is the unescaped body and is_string is true.  |
//| For everything else, 'out' is the raw literal (object, array,    |
//| number, true, false, null).                                      |
//+------------------------------------------------------------------+
bool JsonReadValue(const string &s, int &pos, string &out, bool &is_string)
  {
   is_string = false;
   out = "";
   if(!JsonSkipWs(s, pos))
      return(false);
   const int n = StringLen(s);
   if(pos >= n)
      return(false);
   const ushort c = StringGetCharacter(s, pos);
   if(c == '"')
     {
      is_string = true;
      return(JsonReadString(s, pos, out));
     }
   if(c == '{' || c == '[')
      return(JsonReadBalanced(s, pos, out));

   const int start = pos;
   while(pos < n)
     {
      const ushort d = StringGetCharacter(s, pos);
      if(d == ',' || d == '}' || d == ']' || d == ' ' || d == '\t' || d == '\r' || d == '\n')
         break;
      pos++;
     }
   if(pos <= start)
      return(false);
   out = StringSubstr(s, start, pos - start);
   return(true);
  }

//+------------------------------------------------------------------+
//| Find a key at depth 1 of the given object text (including { }).  |
//| Returns true if the key exists.                                  |
//+------------------------------------------------------------------+
bool JsonGet(const string &obj, const string key, string &out, bool &is_string)
  {
   out = "";
   is_string = false;
   int pos = 0;
   if(!JsonSkipWs(obj, pos))
      return(false);
   if(pos >= StringLen(obj) || StringGetCharacter(obj, pos) != '{')
      return(false);
   pos++; // enter the object
   const int n = StringLen(obj);

   while(pos < n)
     {
      if(!JsonSkipWs(obj, pos))
         return(false);
      const ushort c = StringGetCharacter(obj, pos);
      if(c == '}')
         return(false);
      if(c == ',')
        {
         pos++;
         continue;
        }
      string found_key = "";
      if(!JsonReadString(obj, pos, found_key))
         return(false);
      if(!JsonSkipWs(obj, pos) || StringGetCharacter(obj, pos) != ':')
         return(false);
      pos++; // skip colon
      string value = "";
      bool  val_is_string = false;
      if(!JsonReadValue(obj, pos, value, val_is_string))
         return(false);
      if(found_key == key)
        {
         out = value;
         is_string = val_is_string;
         return(true);
        }
     }
   return(false);
  }

//+------------------------------------------------------------------+
bool JsonHasKey(const string &obj, const string key)
  {
   string dummy;
   bool is_string;
   return(JsonGet(obj, key, dummy, is_string));
  }

//+------------------------------------------------------------------+
string JsonGetString(const string &obj, const string key, const string def = "")
  {
   string raw;
   bool is_string;
   if(!JsonGet(obj, key, raw, is_string))
      return(def);
   if(is_string)
      return(raw);
   if(raw == "null")
      return(def);
   return(raw);
  }

//+------------------------------------------------------------------+
double JsonGetNumber(const string &obj, const string key, const double def, bool &found)
  {
   found = false;
   string raw;
   bool is_string;
   if(!JsonGet(obj, key, raw, is_string))
      return(def);
   if(raw == "" || raw == "null")
      return(def);
   found = true;
   return(StringToDouble(raw));
  }

//+------------------------------------------------------------------+
double JsonGetNumberDef(const string &obj, const string key, const double def = 0.0)
  {
   bool found = false;
   return(JsonGetNumber(obj, key, def, found));
  }

//+------------------------------------------------------------------+
int JsonGetIntDef(const string &obj, const string key, const int def = 0)
  {
   bool found = false;
   const double n = JsonGetNumber(obj, key, (double)def, found);
   if(!found)
      return(def);
   return((int)MathRound(n));
  }

//+------------------------------------------------------------------+
bool JsonGetBool(const string &obj, const string key, const bool def, bool &found)
  {
   found = false;
   string raw;
   bool is_string;
   if(!JsonGet(obj, key, raw, is_string))
      return(def);
   StringToLower(raw);
   if(raw == "true" || raw == "1")
     {
      found = true;
      return(true);
     }
   if(raw == "false" || raw == "0")
     {
      found = true;
      return(false);
     }
   return(def);
  }

//+------------------------------------------------------------------+
bool JsonGetBoolDef(const string &obj, const string key, const bool def = false)
  {
   bool found = false;
   return(JsonGetBool(obj, key, def, found));
  }

//+------------------------------------------------------------------+
//| Return the raw object / array slice for a key, or "".            |
//+------------------------------------------------------------------+
string JsonGetObject(const string &obj, const string key)
  {
   string raw;
   bool is_string;
   if(!JsonGet(obj, key, raw, is_string))
      return("");
   if(is_string)
      return("");
   int pos = 0;
   JsonSkipWs(raw, pos);
   if(pos < StringLen(raw) && StringGetCharacter(raw, pos) == '{')
      return(raw);
   return("");
  }

//+------------------------------------------------------------------+
string JsonGetArray(const string &obj, const string key)
  {
   string raw;
   bool is_string;
   if(!JsonGet(obj, key, raw, is_string))
      return("");
   if(is_string)
      return("");
   int pos = 0;
   JsonSkipWs(raw, pos);
   if(pos < StringLen(raw) && StringGetCharacter(raw, pos) == '[')
      return(raw);
   return("");
  }

//+------------------------------------------------------------------+
//| Split a JSON array into raw element slices (strings unescaped    |
//| and flagged via the parallel is_string array).                   |
//+------------------------------------------------------------------+
int JsonSplitArray(const string &arr, string &items[], bool &is_string[])
  {
   ArrayResize(items, 0);
   ArrayResize(is_string, 0);
   int pos = 0;
   if(!JsonSkipWs(arr, pos))
      return(0);
   if(pos >= StringLen(arr) || StringGetCharacter(arr, pos) != '[')
      return(0);
   pos++;
   const int n = StringLen(arr);
   while(pos < n)
     {
      if(!JsonSkipWs(arr, pos))
         break;
      const ushort c = StringGetCharacter(arr, pos);
      if(c == ']')
         break;
      if(c == ',')
        {
         pos++;
         continue;
        }
      string value = "";
      bool  flag = false;
      if(!JsonReadValue(arr, pos, value, flag))
         break;
      const int k = ArraySize(items);
      ArrayResize(items, k + 1);
      ArrayResize(is_string, k + 1);
      items[k] = value;
      is_string[k] = flag;
     }
   return(ArraySize(items));
  }

//+------------------------------------------------------------------+
//| Strip a UTF-8 BOM and leading/trailing whitespace.               |
//+------------------------------------------------------------------+
string JsonStripNoise(const string &raw)
  {
   string s = raw;
   if(StringLen(s) > 0 && StringGetCharacter(s, 0) == 0xFEFF)
      s = StringSubstr(s, 1);
   // UTF-8 BOM decoded as the three latin chars, just in case
   if(StringLen(s) >= 3 &&
      StringGetCharacter(s, 0) == 0xEF &&
      StringGetCharacter(s, 1) == 0xBB &&
      StringGetCharacter(s, 2) == 0xBF)
      s = StringSubstr(s, 3);
   StringTrimLeft(s);
   StringTrimRight(s);
   return(s);
  }

#endif // GOLD_AI_JSON_MQH
//+------------------------------------------------------------------+
